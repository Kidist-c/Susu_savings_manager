"""Pydantic request/response models. Money fields are strings so no float is ever involved."""
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr


class GroupIn(BaseModel):
    weekly_contribution: StrictStr
    model_config = ConfigDict(json_schema_extra={"examples": [{"weekly_contribution": "50.00"}]})


class GroupOut(BaseModel):
    weekly_contribution: str
    currency: str = "GHS"
    current_week: int