"""Plain frozen dataclasses returned by the service layer. Money is always integer pesewas."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Group:
    weekly_contribution_pesewas: int
    current_week: int


@dataclass(frozen=True)
class Member:
    id: int
    name: str
    join_order: int


@dataclass(frozen=True)
class ContributionResult:
    member: str
    week: int
    paid_pesewas: int
    owed_pesewas: int
    status: str  # "unpaid" | "partial" | "paid"


@dataclass(frozen=True)
class MemberStatus:
    member_id: int
    name: str
    join_order: int
    paid_pesewas: int
    owed_pesewas: int
    status: str


@dataclass(frozen=True)
class Payout:
    week: int
    member: str
    amount_pesewas: int


@dataclass(frozen=True)
class CloseResult:
    payout: Payout
    current_week: int
    next_recipient: str


@dataclass(frozen=True)
class WeekReport:
    current_week: int
    weekly_contribution_pesewas: int
    pot_pesewas: int
    next_recipient: str | None
    members: tuple[MemberStatus, ...]
    total_outstanding_pesewas: int
    payouts: tuple[Payout, ...]
