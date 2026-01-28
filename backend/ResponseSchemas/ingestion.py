from typing import List
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

class ListTranscriptResponse(BaseModel):
    company_id: UUID
    company_name: str
    company_transcripts: List[InsertedTranscript] #list of transcript_ids 

class OrgFreq(BaseModel):
    name: str
    count: int

class Orgs(BaseModel):
    org_unique_count: int
    org_freq: List[OrgFreq]

class ViewTranscriptResponse(BaseModel):
    transcript_id: UUID
    company_id: UUID
    company_name: str
    fiscal_year: int
    fiscal_quarter: int
    transcript_text: str
    org_data : Orgs
