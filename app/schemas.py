"""Pydantic request/response models. Money fields are strings so no float is ever involved."""
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr


class GroupIn(BaseModel):
    weekly_contribution: StrictStr
    model_config = ConfigDict(json_schema_extra={"examples": [{"weekly_contribution": "50.00"}]})


class GroupOut(BaseModel):
    weekly_contribution: str
    currency: str = "GHS"
    current_week: int


class MemberIn(BaseModel):
    name: StrictStr
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "Ama"}]})


class MemberOut(BaseModel):
    id: int
    name: str
    join_order: int


class ContributionIn(BaseModel):
    member: StrictStr
    week: StrictInt
    amount: StrictStr
    model_config = ConfigDict(json_schema_extra={"examples": [{"member": "Esi", "week": 1, "amount": "30.00"}]})


class ContributionOut(BaseModel):
    member: str
    week: int
    paid: str
    owed: str
    status: str


class PayoutOut(BaseModel):
    week: int
    member: str
    amount: str


class CloseOut(BaseModel):
    closed: bool = True
    week: int
    payout: PayoutOut
    current_week: int
    next_recipient: str


class MemberStatusOut(BaseModel):
    name: str
    join_order: int
    paid: str
    paid_pesewas: int
    owed: str
    owed_pesewas: int
    status: str


class ReportOut(BaseModel):
    current_week: int
    currency: str = "GHS"
    weekly_contribution: str
    pot_if_closed: str
    next_recipient: str | None
    members: list[MemberStatusOut]
    total_outstanding: str
    total_outstanding_pesewas: int
    payouts: list[PayoutOut]
