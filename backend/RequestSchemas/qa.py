

from typing import Optional
from pydantic import BaseModel, Field

class IngestRequest(BaseModel):
    company_name_query: str = Optional[Field(min_length=1)] | None
    security_type: str = Field(default="Common Stock")
    exchange_code: str = Field(default="US")
    year: int = Optional[Field(ge=2006, le=2026)] | None 
    quarter: int = Optional[Field(ge=1, le=4)] | None 

class RAGRequest(BaseModel):
    question: str
    company : Optional[IngestRequest] | None = None