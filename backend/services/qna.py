from sqlalchemy.orm import Session

from backend.ResponseSchemas.qa import RAGResponse
from backend.services.rag import embed_chunks, generate_answer, rag_response, retrieve_top_k
from backend.RequestSchemas.qa import RAGRequest
from backend.services.chunking import build_chunks


def ask_ques_svc(ask: RAGRequest, session: Session) -> RAGResponse:
    chunk_response = build_chunks(ask, session)
    embed_chunks(chunk_response, session)
    retrieved = retrieve_top_k(ask, session)
    answer = generate_answer(ask.question, retrieved)
    return rag_response(answer, retrieved)