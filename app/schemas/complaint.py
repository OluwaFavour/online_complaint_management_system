from datetime import datetime
from typing import Optional, Annotated
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, HttpUrl, field_serializer

from ..enums import ComplaintStatus
from .feedback import Feedback


class ComplaintBase(BaseModel):
    type: str
    description: str
    supporting_docs: Annotated[
        Optional[str],
        Field(
            title="Supporting Documents",
            description="List of URLs to the supporting documents separated by space",
        ),
    ]

    @field_serializer("supporting_docs", when_used="json")
    def serialize_supporting_docs(value: Optional[str]) -> list[HttpUrl]:
        return value.split(" ") if value else []


class Complaint(ComplaintBase):
    model_config: ConfigDict = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    created_at: datetime
    status: ComplaintStatus
    feedbacks: list[Feedback]

    @classmethod
    async def model_validate(cls, complaint):
        return cls(
            id=await complaint.awaitable_attrs.id,
            user_id=await complaint.awaitable_attrs.user_id,
            type=await complaint.awaitable_attrs.type,
            description=await complaint.awaitable_attrs.description,
            supporting_docs=await complaint.awaitable_attrs.supporting_docs,
            created_at=await complaint.awaitable_attrs.created_at,
            status=await complaint.awaitable_attrs.status,
        )


class ComplaintCountByStatus(BaseModel):
    status: ComplaintStatus
    count: int
