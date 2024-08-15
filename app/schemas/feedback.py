from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FeedbackBase(BaseModel):
    message: str


class Feedback(FeedbackBase):
    model_config: ConfigDict = ConfigDict(from_attributes=True)
    id: UUID
    message_id: str
    user_id: UUID
    complaint_id: UUID
    created_at: datetime
