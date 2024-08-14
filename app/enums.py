from enum import Enum


class ComplaintStatus(Enum):
    NEW = "new"
    PENDING = "pending"
    PAUSED = "paused"
    RESOLVED = "resolved"


class TokenType(Enum):
    ACCESS = "access"
    REFRESH = "refresh"
