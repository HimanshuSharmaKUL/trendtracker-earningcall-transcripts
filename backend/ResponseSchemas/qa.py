

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

class Sources(BaseModel):
    company_id: UUID
    transcript_id: UUID
    chunk_id: UUID
    speaker: Optional[str]
    paragraph_num: Optional[int]
    score: float
    snippet: str

class RAGResponse(BaseModel):
    answer: str
    sources: List[Sources]
