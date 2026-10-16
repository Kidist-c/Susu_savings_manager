"""Domain exceptions. Each carries a stable machine-readable code and a human message.

They know nothing about HTTP; app/main.py maps codes to status codes.
"""


class SusuError(Exception):
    code = "error"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidMoney(SusuError):
    code = "invalid_money"


class NonPositiveAmount(SusuError):
    code = "amount_must_be_positive"


class GroupNotFound(SusuError):
    code = "group_not_found"

    def __init__(self):
        super().__init__("No group exists yet. Create one with POST /group.")


class GroupAlreadyExists(SusuError):
    code = "group_already_exists"

    def __init__(self):
        super().__init__("A group already exists. Only one group is supported.")


class InvalidName(SusuError):
    code = "invalid_name"


class GroupAlreadyStarted(SusuError):
    code = "group_already_started"

    def __init__(self):
        super().__init__("Members can only be added before the first contribution is recorded.")


class DuplicateMember(SusuError):
    code = "duplicate_member"

    def __init__(self, name: str):
        super().__init__(f"A member named '{name}' already exists (names are not case-sensitive).", {"name": name})


class UnknownMember(SusuError):
    code = "unknown_member"

    def __init__(self, name: str):
        super().__init__(f"No member named '{name}'.", {"name": name})


class WeekNotOpen(SusuError):
    code = "week_not_open"

    def __init__(self, week: int, current_week: int):
        super().__init__(
            f"Week {week} is not open yet; the current week is {current_week}.",
            {"week": week, "current_week": current_week},
        )


class WeekAlreadyClosed(SusuError):
    code = "week_already_closed"

    def __init__(self, week: int, current_week: int):
        super().__init__(
            f"Week {week} is already closed; the current week is {current_week}.",
            {"week": week, "current_week": current_week},
        )


class Overpayment(SusuError):
    code = "overpayment"

    def __init__(self, name: str, remaining: str, attempted: str):
        super().__init__(
            f"{name} owes {remaining} this week; {attempted} is too much.",
            {"member": name, "remaining": remaining},
        )


class NoMembers(SusuError):
    code = "no_members"

    def __init__(self):
        super().__init__("The group has no members, so there is nobody to collect from or pay.")


class WeekIncomplete(SusuError):
    code = "week_incomplete"

    def __init__(self, week: int, outstanding: list[dict]):
        count = len(outstanding)
        super().__init__(
            f"Week {week} cannot close: {count} member{'s' if count != 1 else ''} still owe{'' if count != 1 else 's'} money.",
            {"week": week, "outstanding": outstanding},
        )


class ConcurrentModification(SusuError):
    code = "concurrent_modification"

    def __init__(self):
        super().__init__("The group changed while closing the week. Nothing was changed; please retry.")
