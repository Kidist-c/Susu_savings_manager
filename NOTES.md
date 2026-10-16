# NOTES: assumptions, decisions, trade-offs, limitations

The challenge leaves several behaviours open. Each is decided below, with the reason, the alternatives, the
trade-off, where it is enforced and where it is tested. Test names are in `tests/`.

## Design overview

- **Money is integer pesewas** (GHS 1.00 = 100). `app/money.py` parses text with a strict pattern and integer
  arithmetic and formats back to `"50.00"`. `Decimal` would also be exact, but SQLite has no decimal type
  (NUMERIC/REAL columns become binary floats), so integers store natively and sum exactly in SQL. A test checks
  that the code never uses `float`.
- **Business rules are separate from HTTP.** `app/services.py` takes a database connection and never imports
  FastAPI, so every rule is tested without a web server. `app/main.py` only translates requests and errors.
- **Recording a payment and closing a week are different operations.** Payments are an append-only ledger.
  Owed amounts, status and the pot are *derived* from it, never stored, so they cannot drift out of sync.
  Closing is an explicit action; it never happens automatically when the last payment arrives.
- **Closing a week is one SQLite transaction** (`BEGIN IMMEDIATE`): insert the payout and advance the week
  together or not at all. Extra guards: `UNIQUE(week)` on payouts and `UPDATE ... WHERE current_week = ?`.
  If anyone still owes money, nothing at all is written.
- **Validation order is fixed** so the same bad request always gives the same error: money format, positive,
  group exists, member exists, week, overpayment.

## Decisions

### D1. Membership is frozen once the group starts
- **Decision:** members can be added only while no contribution exists and the group is in week 1. Afterwards
  `POST /members` returns 409 `group_already_started`.
- **Why:** the recipient formula needs a stable member list. A late joiner would shift positions, could cause
  skipped or repeated recipients, and would owe nothing for earlier weeks.
- **Alternatives:** allow joining between weeks with a "fewest payouts, then join order" rule; allow joining any time.
- **Trade-off:** simple and fair, but less flexible than real groups.
- **Enforced:** `services.add_member`. **Tested:** `test_add_member_after_first_contribution_rejected`.
- Closing a group with no members returns 409 `no_members` (`test_close_with_no_members_rejected`).

### D2. Names are unique after trimming and case-folding
- `Ama`, `" ama "` and `AMA` are the same member. The stored name is the trimmed original; the key is
  `name.strip().casefold()`. Blank names and names over 100 characters are rejected (422 `invalid_name`).
- **Alternatives:** case-sensitive names; caller-supplied ids. **Trade-off:** two real people with the same name
  cannot both join (use "Ama B.").
- **Enforced:** service check plus `UNIQUE(name_key)`. **Tested:** `test_members.py`.
- Contributions look members up the same way (so `"ama"` pays for Ama).

### D3. Several partial payments per week are allowed
- Each payment is one ledger row; the member owes `fixed - sum(payments this week)`.
- **Trade-off:** a client that retries a *partial* payment after a timeout can double-record it (see limitations).
- **Tested:** `test_multiple_partials_complete_exactly`, `test_overpayment_after_partial_uses_remaining_amount`.

### D4. Contributions name the week, and it must be the current week
- Future week: 409 `week_not_open`. Past (closed) week: 409 `week_already_closed`.
- **Why:** explicit weeks match "for a specified week" and stop a client paying week 2 while the server applies
  it to week 1. Prepayment and back-payment are not defined by the rules, so they are not supported.
- **Enforced:** `services.record_contribution`. **Tested:** `test_future_week_rejected`,
  `test_past_week_rejected_after_week_advances`.
- Payments above the *remaining* amount (including any payment from someone who already paid in full) are 409
  `overpayment`.

### D5. Payments cannot be edited or deleted
- The ledger is append-only and there are no such endpoints (PUT/PATCH/DELETE on `/contributions` return 405).
- **Why:** payouts depend on payments; changing history would make payout records inconsistent.
- **Trade-off:** a mistaken payment cannot be undone. Reversal entries would be the fix.

### D6. Closing a week twice is rejected
- The week number is in the URL and must equal the current week. A lower number is 409 `week_already_closed`, a
  higher one 409 `week_not_open`. A stale retry therefore can never close the *next* week and can never pay twice.
- **Alternatives:** idempotent 200 that replays the payout; a body-less "close current week" endpoint (dangerous:
  a retry would close week 2).
- **Enforced:** week comparison, `UNIQUE(week)`, guarded UPDATE. **Tested:** `test_double_close_creates_one_payout`,
  `test_payout_week_is_unique_in_database`, `test_close_is_atomic_when_week_update_fails`.

### D7. Pot = weekly contribution x member count; the recipient also contributes
- This matches the required example (3 x 50.00 = 150.00 paid to Ama, who also paid 50.00). If the recipient were
  exempt the pot would be 100.00, contradicting the example.
- **Tested:** `test_pot_scales_with_member_count`, `test_recipient_must_also_pay`.

### D8. Rotation wraps after the last member
- Recipient of week *w* is member `((w - 1) mod N) + 1` in joining order, so week 4 of a 3-member group pays the
  first member again and the group continues indefinitely. **Alternative:** end the group after N weeks.
- **Tested:** `test_rotation_follows_join_order_and_wraps`.

### D9. An incomplete week stays the current week
- A blocked close (409 `week_incomplete`, listing each member and the exact amount owed) changes nothing.
  Skipping a week would change who is paid and when, which the rules do not allow.
- **Trade-off:** one member who never pays blocks the group; handling that is outside this challenge.
- **Tested:** `test_failed_close_changes_nothing`, `test_failed_close_leaves_report_identical`.

### D10. Invalid money is rejected, never rounded
- Amounts are strings with at most 2 decimals. `"50.123"`, `"1,000"`, `"1e3"`, `"GHS 50"` are 422 `invalid_money`.
  Zero and negative amounts are 422 `amount_must_be_positive`. JSON numbers (already floats) are rejected by the
  schema. A sanity limit of GHS 1,000,000.00 applies.
- **Tested:** `test_money.py` (parametrized valid/invalid tables, 0.10 + 0.20, ten x 0.10 = 1.00).

### Smaller decisions
- One group only; a second `POST /group` is 409.
- Currency is always GHS; requests carry no currency field.
- Members are addressed by name (trimmed, case-insensitive); responses also include the numeric id.
- Status values: `unpaid` (paid nothing), `partial`, `paid`.
- A blocked close is HTTP 409 (a conflict with the current state) with the outstanding list in the body.
- Timestamps are UTC ISO-8601 and never used in business rules.

## Alternatives considered

`Decimal` instead of integer pesewas; SQLAlchemy instead of plain `sqlite3`; idempotent close; late joiners;
ending the group after N weeks; defaulting the week when omitted.

## Known limitations

- A single group; no authentication or authorisation.
- No payment edits or reversals.
- A retried *partial* payment is recorded twice (no idempotency key).
- Membership is frozen after the first contribution.
- SQLite is suited to low concurrency; writes are serialised (`BEGIN IMMEDIATE`).
- No reset endpoint; delete the database file to start over locally.
- No deployment has been done; on typical free hosting the local SQLite file would not persist.

## With more time

Idempotency keys for contributions, reversal entries, late joiners with a payout-count rule, a "cycle complete"
state, multiple groups, authentication, schema migrations, and a CI workflow running `pytest`.
