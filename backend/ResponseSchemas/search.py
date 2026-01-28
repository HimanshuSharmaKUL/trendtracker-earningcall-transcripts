from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class TranscriptHit(BaseModel):
    transcript_id: UUID
    company_id: UUID
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    rank: float
    snippet: str

class QueryResponse(BaseModel):
    total: int
    hits: List[TranscriptHit]

