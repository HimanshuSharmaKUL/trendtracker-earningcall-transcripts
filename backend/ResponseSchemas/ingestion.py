from uuid import UUID
from pydantic import BaseModel

class CompanyResp(BaseModel):
    company_id: UUID #uuid of company
    name: str #common name
    ticker: str

class InsertedTranscript(BaseModel):
    transcript_id: UUID #uuid of transcript
    fiscal_year: int
    fiscal_quarter: int

class IngestionResponse(BaseModel):
    company_id: UUID #uuid of company
    company_name: str #common name
    ticker: str
    transcript_id: UUID #uuid of transcript
    fiscal_year: int
    fiscal_quarter: int