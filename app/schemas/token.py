from datetime import datetime

from pydantic import BaseModel

from ..enums import TokenType


class Token(BaseModel):
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str | None
    refresh_token_expires_at: datetime | None
    token_type: str
