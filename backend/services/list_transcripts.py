#handle the list transcript get requests
#list the transcripts for a given company
#display the transcript text
#display extracted organisation entities
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.RequestSchemas.ingestion import IngestRequest, ListRequest
from backend.ResponseSchemas.ingestion import InsertedTranscript, ListTranscriptResponse, OrgFreq, Orgs, ViewTranscriptResponse
from backend.models.companies_transcripts import Company, EarningCallTranscript
from backend.services.ticker_from_company import _api_call, resolve_company_to_ticker


def list_transcript_svc(req: str, session: Session):
    req_query = IngestRequest(
        company_name_query= req,
        security_type="Common Stock",
        exchange_code= "US",
        year=2025, #not used,
        quarter=1 #not used
    )
    resolved = resolve_company_to_ticker(req_query)
    print("Resolved company tick:", resolved.ticker)
    company_exist = session.query(Company).filter(Company.ticker==resolved.ticker).first()

    if not company_exist:
        raise HTTPException(status_code=404, detail="Company does not exist in database.")
    
    transcripts = (
        session.query(EarningCallTranscript).filter(EarningCallTranscript.company_id == company_exist.id)
        .order_by(EarningCallTranscript.fiscal_year.desc(),
                  EarningCallTranscript.fiscal_quarter.desc()).all()
    )

    
    company_transcripts = [InsertedTranscript(
                transcript_id= transc.id,
                fiscal_year= transc.fiscal_year,
                fiscal_quarter= transc.fiscal_quarter
            ) for transc in transcripts]

    return ListTranscriptResponse(
        company_id=company_exist.id,
        company_name=company_exist.name,
        company_transcripts= company_transcripts
    )

def view_transcript_svc(transcript_id: str, session: Session):
    try:
        transcript_uuid = UUID(transcript_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transcript_id format.")
    
    transcript = (session.query(EarningCallTranscript).filter(EarningCallTranscript.id == transcript_uuid).first())
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    
    org_data = transcript.org_data or {}
    raw_freq_list = (org_data.get("org_freq_count_sorted") or org_data.get("org_freq") or [])
    org_freq = [OrgFreq(name=item.get("name", ""), count=int(item.get("count", 0))) for item in raw_freq_list ]
    org_unique_count = org_data.get("org_unique_count")
    company = session.query(Company.name).filter(Company.id==transcript.company_id).first()
    return ViewTranscriptResponse(
        transcript_id = transcript.id,
        company_id = transcript.company_id,
        company_name= company.name,
        fiscal_year = transcript.fiscal_year,
        fiscal_quarter = transcript.fiscal_quarter,
        transcript_text = transcript.raw_text,
        org_data = Orgs(
            org_unique_count = org_unique_count,
            org_freq = org_freq
        ),)
    