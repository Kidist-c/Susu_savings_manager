from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_group_over_http(tmp_path, monkeypatch):
    monkeypatch.setenv("SUSU_DB_PATH", str(tmp_path / "test.db"))
    client = TestClient(app)
    response = client.post("/group", json={"weekly_contribution": "50.00"})
    assert response.status_code == 201
    assert response.json() == {"weekly_contribution": "50.00", "currency": "GHS", "current_week": 1}
    again = client.post("/group", json={"weekly_contribution": "50.00"})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "group_already_exists"
    bad = client.post("/group", json={"weekly_contribution": "0"})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "amount_must_be_positive"
    as_number = client.post("/group", json={"weekly_contribution": 50.5})
    assert as_number.status_code == 422


def test_members_over_http(tmp_path, monkeypatch):
    monkeypatch.setenv("SUSU_DB_PATH", str(tmp_path / "test.db"))
    client = TestClient(app)
    no_group = client.post("/members", json={"name": "Ama"})
    assert no_group.status_code == 404
    assert no_group.json()["error"]["code"] == "group_not_found"
    client.post("/group", json={"weekly_contribution": "50.00"})
    for name in ("Ama", "Kofi", "Esi"):
        assert client.post("/members", json={"name": name}).status_code == 201
    duplicate = client.post("/members", json={"name": " ama "})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_member"
    listing = client.get("/members").json()
    assert [m["name"] for m in listing] == ["Ama", "Kofi", "Esi"]
    assert [m["join_order"] for m in listing] == [1, 2, 3]


def test_contribution_errors_over_http(tmp_path, monkeypatch):
    monkeypatch.setenv("SUSU_DB_PATH", str(tmp_path / "test.db"))
    client = TestClient(app)
    client.post("/group", json={"weekly_contribution": "50.00"})
    for name in ("Ama", "Kofi", "Esi"):
        client.post("/members", json={"name": name})

    ok = client.post("/contributions", json={"member": "Esi", "week": 1, "amount": "30.00"})
    assert ok.status_code == 201
    assert ok.json() == {"member": "Esi", "week": 1, "paid": "30.00", "owed": "20.00", "status": "partial"}

    def error_of(payload):
        response = client.post("/contributions", json=payload)
        return response.status_code, response.json()["error"]["code"]

    assert error_of({"member": "Kwame", "week": 1, "amount": "10.00"}) == (404, "unknown_member")
    assert error_of({"member": "Esi", "week": 1, "amount": "25.00"}) == (409, "overpayment")
    assert error_of({"member": "Esi", "week": 2, "amount": "5.00"}) == (409, "week_not_open")
    assert error_of({"member": "Esi", "week": 1, "amount": "0"}) == (422, "amount_must_be_positive")
    assert error_of({"member": "Esi", "week": 1, "amount": "1.234"}) == (422, "invalid_money")
    number = client.post("/contributions", json={"member": "Esi", "week": 1, "amount": 5.1})
    assert number.status_code == 422
    assert client.delete("/contributions").status_code == 405
    assert client.put("/contributions").status_code == 405


def test_close_week_over_http(tmp_path, monkeypatch):
    monkeypatch.setenv("SUSU_DB_PATH", str(tmp_path / "test.db"))
    client = TestClient(app)
    client.post("/group", json={"weekly_contribution": "50.00"})
    for name in ("Ama", "Kofi", "Esi"):
        client.post("/members", json={"name": name})
    for name, amount in (("Ama", "50.00"), ("Kofi", "50.00"), ("Esi", "30.00")):
        client.post("/contributions", json={"member": name, "week": 1, "amount": amount})

    blocked = client.post("/weeks/1/close")
    assert blocked.status_code == 409
    error = blocked.json()["error"]
    assert error["code"] == "week_incomplete"
    assert error["details"]["outstanding"] == [{"member": "Esi", "owed": "20.00"}]

    assert client.post("/weeks/2/close").status_code == 409  # wrong week
    client.post("/contributions", json={"member": "Esi", "week": 1, "amount": "20.00"})
    done = client.post("/weeks/1/close")
    assert done.status_code == 200
    assert done.json() == {
        "closed": True, "week": 1, "payout": {"week": 1, "member": "Ama", "amount": "150.00"},
        "current_week": 2, "next_recipient": "Kofi",
    }
    again = client.post("/weeks/1/close")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "week_already_closed"
    assert client.post("/weeks/0/close").status_code == 422


def test_required_example_end_to_end(tmp_path, monkeypatch):
    """The challenge example, over HTTP, from an empty database."""
    monkeypatch.setenv("SUSU_DB_PATH", str(tmp_path / "test.db"))
    client = TestClient(app)
    assert client.post("/group", json={"weekly_contribution": "50.00"}).status_code == 201
    for name in ("Ama", "Kofi", "Esi"):
        assert client.post("/members", json={"name": name}).status_code == 201
    for name, amount in (("Ama", "50.00"), ("Kofi", "50.00"), ("Esi", "30.00")):
        assert client.post("/contributions", json={"member": name, "week": 1, "amount": amount}).status_code == 201

    blocked = client.post("/weeks/1/close")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["details"]["outstanding"] == [{"member": "Esi", "owed": "20.00"}]
    assert client.get("/report").json()["payouts"] == []  # no payout, still week 1
    assert client.get("/report").json()["current_week"] == 1

    assert client.post("/contributions", json={"member": "Esi", "week": 1, "amount": "20.00"}).status_code == 201
    done = client.post("/weeks/1/close")
    assert done.status_code == 200
    assert done.json()["payout"]["member"] == "Ama" and done.json()["payout"]["amount"] == "150.00"

    report = client.get("/report").json()
    assert report["current_week"] == 2
    assert report["next_recipient"] == "Kofi"
    assert report["payouts"] == [{"week": 1, "member": "Ama", "amount": "150.00"}]
    assert report["total_outstanding"] == "150.00"
    assert [m["status"] for m in report["members"]] == ["unpaid", "unpaid", "unpaid"]


def test_report_without_group_is_404(tmp_path, monkeypatch):
    monkeypatch.setenv("SUSU_DB_PATH", str(tmp_path / "test.db"))
    response = TestClient(app).get("/report")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "group_not_found"
