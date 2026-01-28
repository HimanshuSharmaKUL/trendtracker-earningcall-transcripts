from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class QueryRequest(BaseModel):
    query: str
    company_id: Optional[UUID] | None = None
    fiscal_year: Optional[int] | None  = None
    fiscal_quarter: Optional[int] |None = None
    limit: int = 20 #return atmost 20 hits
    offset: int = 0 #start from the top, or skip no rows before returning the results