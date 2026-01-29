

from typing import Optional
from pydantic import BaseModel, Field

class IngestRequest(BaseModel):
    company_name_query: Optional[str] = [Field(min_length=1, default=None)]  
    security_type: Optional[str] = Field(default="Common Stock")
    exchange_code: Optional[str] = Field(default="US")
    year: Optional[int] =  Field(ge=2006, le=2026, default=None) 
    quarter: Optional[int] = Field(ge=1, le=4, default=None) 

class RAGRequest(BaseModel):
    question: str
    company : Optional[IngestRequest] = None