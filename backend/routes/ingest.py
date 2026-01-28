from fastapi import APIRouter, Depends, status
from backend.RequestSchemas.ingestion import IngestRequest, ListRequest
from backend.ResponseSchemas.ingestion import IngestionResponse, ListTranscriptResponse, ViewTranscriptResponse
from backend.config.database import get_session
from backend.services.ingestion import ingest_request
from sqlalchemy.orm import Session

from backend.services.list_transcripts import list_transcript_svc, view_transcript_svc

ingest_router = APIRouter(
    prefix="/ingest",
    tags=["Ingestion"],
    responses={
        404: {"description": "Not Found"}
    },  # default response - eg: if a route path is not defined then 404 will be thrown
)


@ingest_router.post("/ingest-in", status_code=status.HTTP_201_CREATED, response_model=IngestionResponse)
async def ingest(req: IngestRequest, session: Session = Depends(get_session)):
    return await ingest_request(req, session)

@ingest_router.get("/ingest-out/{req}", status_code=status.HTTP_201_CREATED, response_model=ListTranscriptResponse)
def list_transcripts(req: str , session: Session = Depends(get_session)):
    return list_transcript_svc(req, session)

@ingest_router.get("/view/{transcript_id}", status_code=status.HTTP_201_CREATED, response_model=ViewTranscriptResponse)
def view_transcripts(transcript_id: str, session: Session = Depends(get_session)):
    return view_transcript_svc(transcript_id, session)
    