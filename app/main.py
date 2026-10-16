"""HTTP layer: routes only. Business rules live in app/services.py."""
from fastapi import Depends, FastAPI, Path
from fastapi.responses import JSONResponse

from app import schemas, services
from app.database import connect
from app.errors import SusuError
from app.money import format_ghs

app = FastAPI(
    title="Susu Savings Manager",
    version="1.0.0",
    description="Manage one rotating savings group (susu). Money is exact: amounts are strings like '50.00' (GHS).",
)

# Domain error code -> HTTP status. 404 = missing thing, 409 = conflicts with current state,
# 422 = the input itself is invalid.
HTTP_STATUS = {
    "invalid_money": 422,
    "amount_must_be_positive": 422,
    "invalid_name": 422,
    "group_not_found": 404,
    "unknown_member": 404,
    "group_already_exists": 409,
    "group_already_started": 409,
    "duplicate_member": 409,
    "week_not_open": 409,
    "week_already_closed": 409,
    "overpayment": 409,
    "week_incomplete": 409,
    "no_members": 409,
    "concurrent_modification": 409,
}


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@app.exception_handler(SusuError)
async def susu_error_handler(request, exc: SusuError):
    return JSONResponse(
        status_code=HTTP_STATUS.get(exc.code, 400),
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/group", response_model=schemas.GroupOut, status_code=201)
def create_group(body: schemas.GroupIn, conn=Depends(get_conn)):
    group = services.create_group(conn, body.weekly_contribution)
    return {"weekly_contribution": format_ghs(group.weekly_contribution_pesewas), "current_week": group.current_week}


@app.post("/members", response_model=schemas.MemberOut, status_code=201)
def add_member(body: schemas.MemberIn, conn=Depends(get_conn)):
    member = services.add_member(conn, body.name)
    return {"id": member.id, "name": member.name, "join_order": member.join_order}


@app.get("/members", response_model=list[schemas.MemberOut])
def list_members(conn=Depends(get_conn)):
    return [{"id": m.id, "name": m.name, "join_order": m.join_order} for m in services.list_members(conn)]


@app.post("/contributions", response_model=schemas.ContributionOut, status_code=201)
def record_contribution(body: schemas.ContributionIn, conn=Depends(get_conn)):
    result = services.record_contribution(conn, body.member, body.week, body.amount)
    return {
        "member": result.member,
        "week": result.week,
        "paid": format_ghs(result.paid_pesewas),
        "owed": format_ghs(result.owed_pesewas),
        "status": result.status,
    }


@app.post("/weeks/{week_number}/close", response_model=schemas.CloseOut)
def close_week(week_number: int = Path(ge=1, description="The week you intend to close (must be the current week)."),
               conn=Depends(get_conn)):
    result = services.close_week(conn, week_number)
    return {
        "closed": True,
        "week": result.payout.week,
        "payout": {
            "week": result.payout.week,
            "member": result.payout.member,
            "amount": format_ghs(result.payout.amount_pesewas),
        },
        "current_week": result.current_week,
        "next_recipient": result.next_recipient,
    }


@app.get("/report", response_model=schemas.ReportOut)
def report(conn=Depends(get_conn)):
    r = services.get_report(conn)
    return {
        "current_week": r.current_week,
        "weekly_contribution": format_ghs(r.weekly_contribution_pesewas),
        "pot_if_closed": format_ghs(r.pot_pesewas),
        "next_recipient": r.next_recipient,
        "members": [
            {
                "name": m.name,
                "join_order": m.join_order,
                "paid": format_ghs(m.paid_pesewas),
                "paid_pesewas": m.paid_pesewas,
                "owed": format_ghs(m.owed_pesewas),
                "owed_pesewas": m.owed_pesewas,
                "status": m.status,
            }
            for m in r.members
        ],
        "total_outstanding": format_ghs(r.total_outstanding_pesewas),
        "total_outstanding_pesewas": r.total_outstanding_pesewas,
        "payouts": [
            {"week": p.week, "member": p.member, "amount": format_ghs(p.amount_pesewas)} for p in r.payouts
        ],
    }
