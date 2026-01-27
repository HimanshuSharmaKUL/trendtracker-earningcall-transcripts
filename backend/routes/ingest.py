from fastapi import APIRouter, Depends, status
from backend.RequestSchemas.ingestion import IngestRequest
from backend.ResponseSchemas.ingestion import IngestionResponse
from backend.config.database import get_session
from backend.services.ingestion import ingest_request
from sqlalchemy.orm import Session

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
    