from fastapi import HTTPException
from backend.RequestSchemas.ingestion import IngestRequest
from backend.ResponseSchemas.ingestion import IngestionResponse
from backend.services.fetch_transcripts import store_transcripts
from backend.services.ticker_from_company import resolve_company_to_ticker



async def ingest_request(req: IngestRequest, session) -> IngestionResponse:
    resolved_company_response = resolve_company_to_ticker(req)
    # result = await svc.ingest(req.company_name, req.max_transcripts)
    persistance_response = store_transcripts(resolved_company_response, req, session)
    #  'company_id': company.id,
    #     'company_ticker':company.ticker,
    #     'company_name':company.name,
    #     'inserted_transcript_id': transcript.id,
    #     'year': transcript.fiscal_year,
    #     'quarter': transcript.fiscal_quarter
    return IngestionResponse(
        company_id = persistance_response.get('company_id'),
        company_name = persistance_response.get('company_name'),
        ticker = persistance_response.get('company_ticker'),
        transcript_id = persistance_response.get('inserted_transcript_id'),
        fiscal_year = persistance_response.get('year'),
        fiscal_quarter = persistance_response.get('quarter')
    )

    
