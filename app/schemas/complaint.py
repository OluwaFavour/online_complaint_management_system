from typing import Optional, Annotated

from pydantic import BaseModel, Field, ConfigDict, HttpUrl

from ..enums import ComplaintStatus


class ComplaintBase(BaseModel):
    type: str
    description: str
    supporting_docs: Annotated[
        Optional[HttpUrl],
        Field(
            title="Supporting Documents",
            description="URL to cloudinary <user_id>/<complaint>/supporting_docs folder",
        ),
    ]


class ComplaintCreate(ComplaintBase):
    pass


class Complaint(ComplaintBase):
    model_config: ConfigDict = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    created_at: str
    status: ComplaintStatus
