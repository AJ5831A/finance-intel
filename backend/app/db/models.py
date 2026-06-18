from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON


class Contract(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_path: str
    format: str
    status: str = "uploaded"          # uploaded|processing|done|failed
    error: Optional[str] = None
    analysis: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class FollowUpMessage(SQLModel, table=True):
    """One turn in the human-in-the-loop follow-up conversation for a filing.

    One shared thread per contract; ordered by created_at. Persisted (unlike the
    in-process progress store) so it survives reloads and restarts.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    contract_id: int = Field(index=True, foreign_key="contract.id")
    role: str                          # user|assistant
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
