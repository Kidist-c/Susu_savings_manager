# Susu Savings Manager

A small FastAPI service that manages **one rotating savings group (susu)** in Ghanaian cedis (GHS).

Every member contributes the same fixed amount each week. When *everyone* has paid in full, the whole pot is paid
to one member (in the order members joined) and the next week begins. If anyone is short, nobody is paid and the
service reports exactly who owes how much.

There is no user interface: just a JSON API with automatic interactive documentation.

## Features

- Create a group with a fixed weekly contribution (e.g. `50.00`)
- Add members (unique names, case-insensitive); the joining order sets the payout order
- Record full or partial contributions for the current week (several partial payments are fine)
- Close a week: blocked with an exact "who owes what" report, or paid out and advanced atomically
- Report: current week, each member's paid / owed / status, outstanding total, payout history
- Exact money: integer pesewas, no floating point anywhere
- Data persists in SQLite across restarts

## Requirements

- Python 3.11 or newer
- Packages in `requirements.txt` (FastAPI, Uvicorn, Pydantic, pytest, httpx)

## Setup (virtual environment)

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the API

```bash
uvicorn app.main:app --reload
```

The API is at <http://127.0.0.1:8000>. Data is stored in `susu.db` in the project folder (git-ignored).
Set the `SUSU_DB_PATH` environment variable to use a different file. To start from scratch, stop the server and
delete the database file.

## Run the tests

```bash
pytest -q
```

Tests use in-memory or temporary SQLite databases and FastAPI's in-process `TestClient`, so no server needs to be
running.

## Inspect the API documentation

With the server running:

- <http://127.0.0.1:8000/docs> - interactive Swagger UI. Use **Try it out** to run the whole example below by clicking.
- <http://127.0.0.1:8000/redoc> - read-only reference
- <http://127.0.0.1:8000/openapi.json> - machine-readable spec

## Endpoints

| Method and path | Purpose | Success |
|---|---|---|
| `POST /group` | Create the group `{"weekly_contribution": "50.00"}` | 201 |
| `POST /members` | Add a member `{"name": "Ama"}` | 201 |
| `GET /members` | List members in joining order | 200 |
| `POST /contributions` | Record a payment `{"member": "Esi", "week": 1, "amount": "30.00"}` | 201 |
| `POST /weeks/{week_number}/close` | Try to close a week (must be the current week) | 200 |
| `GET /report` | Current status and payout history | 200 |
| `GET /health` | Health check | 200 |

Money is always a **string** such as `"50.00"` (at most 2 decimals). JSON numbers are rejected on purpose.

Errors share one shape: `{"error": {"code": "...", "message": "...", "details": {...}}}`.

| Status | Meaning | Codes |
|---|---|---|
| 404 | Something does not exist | `group_not_found`, `unknown_member` |
| 409 | Conflicts with the current state | `group_already_exists`, `group_already_started`, `duplicate_member`, `week_not_open`, `week_already_closed`, `overpayment`, `week_incomplete`, `no_members`, `concurrent_modification` |
| 422 | The input itself is invalid | `invalid_money`, `amount_must_be_positive`, `invalid_name` (plus FastAPI's standard 422 for wrong field types) |

## Complete example: Ama, Kofi and Esi

```bash
BASE=http://127.0.0.1:8000
H='Content-Type: application/json'

curl -s -X POST $BASE/group -H "$H" -d '{"weekly_contribution": "50.00"}'
for n in Ama Kofi Esi; do curl -s -X POST $BASE/members -H "$H" -d "{\"name\": \"$n\"}"; done

curl -s -X POST $BASE/contributions -H "$H" -d '{"member":"Ama","week":1,"amount":"50.00"}'
curl -s -X POST $BASE/contributions -H "$H" -d '{"member":"Kofi","week":1,"amount":"50.00"}'
curl -s -X POST $BASE/contributions -H "$H" -d '{"member":"Esi","week":1,"amount":"30.00"}'

# Blocked: nobody is paid, the week does not advance
curl -s -i -X POST $BASE/weeks/1/close
# -> 409 {"error":{"code":"week_incomplete",...,"details":{"week":1,"outstanding":[{"member":"Esi","owed":"20.00"}]}}}

curl -s -X POST $BASE/contributions -H "$H" -d '{"member":"Esi","week":1,"amount":"20.00"}'

# Success: Ama receives 150.00 and week 2 begins with Kofi next
curl -s -X POST $BASE/weeks/1/close
# -> {"closed":true,"week":1,"payout":{"week":1,"member":"Ama","amount":"150.00"},"current_week":2,"next_recipient":"Kofi"}

curl -s $BASE/report
```

## How it is organised

```
app/main.py       HTTP routes only; maps domain errors to status codes
app/schemas.py    Pydantic request/response models
app/services.py   ALL business rules (no FastAPI imports), tested directly
app/models.py     small frozen dataclasses returned by services
app/database.py   SQLite connection, schema, transaction helpers
app/money.py      text <-> integer pesewas
app/errors.py     domain exceptions with stable codes
tests/            pytest suite (service, persistence and API tests)
```

Design decisions, assumptions, trade-offs and limitations are in [NOTES.md](NOTES.md).

## Live demo

None. No deployment has been done for this project.
