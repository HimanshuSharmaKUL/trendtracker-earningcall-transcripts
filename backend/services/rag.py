from datetime import datetime, timezone
import json
from typing import List, Tuple
import requests
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, select

from backend.RequestSchemas.qa import RAGRequest
from backend.ResponseSchemas.qa import RAGResponse, Sources
from backend.config.config import get_settings
from backend.config.embeddings import get_embedding_model
from backend.models.companies_transcripts import EarningCallTranscript, TranscriptChunk
from backend.services.InternalSchemas.chunk import Chunk
from backend.services.ticker_from_company import resolve_company_to_ticker


settings = get_settings()

def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_embedding_model()
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
    
    return [e.tolist() for e in embeddings]

def _deduplicate_chunks(chunks: List[Chunk]) -> List[Chunk]:
    seen = set()
    unique = []
    for ch in chunks:
        key = (ch.transcript_id, ch.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(ch)
    return unique


def _upsert_chunk(session: Session, chunk, emb: List[float]):
    row = session.execute(select(TranscriptChunk).where(
            TranscriptChunk.transcript_id == chunk.transcript_id,
            TranscriptChunk.chunk_id == chunk.chunk_id,
        )).scalar_one_or_none() #unique (transcript_id, chunk_id) in TranscriptChunk table
    
    if row is None:
        row = TranscriptChunk(
            transcript_id= chunk.transcript_id,
            company_id= chunk.company_id,
            chunk_id= chunk.chunk_id,
            chunk_hash = chunk.chunk_hash,
            chunk_index= chunk.chunk_index,
            embedding = emb, #384 size in db
            embedding_model = get_settings().EMBEDDING_MODEL if emb is not None else None,
            updated_at = datetime.now(timezone.utc) if emb is not None else None,
            chunk_data = chunk.chunk_data,
        )
        session.add(row)
    else: #fill missing fields or update embedding if absent and refresh the previous fields
        if row.embedding is None and emb is not None:
            row.embedding = emb
            row.embedding_model = get_settings().EMBEDDING_MODEL
            row.updated_at = datetime.now(timezone.utc)
            row.chunk_data = chunk.chunk_data

    return row

def embed_chunks(chunks: List[Chunk], session: Session) -> None:
    #if there are existing chinks with embeddings
    chunks = _deduplicate_chunks(chunks)
    existing = {(transcr_id,chunk_id) for (transcr_id, chunk_id) in (session.query(TranscriptChunk.transcript_id, TranscriptChunk.chunk_id)
                                            .filter(TranscriptChunk.chunk_id.in_([ch.chunk_id for ch in chunks]))
                                            .filter(TranscriptChunk.embedding.isnot(None))
                                            .all() )}
    
    to_embed = [ch for ch in chunks if (ch.transcript_id,ch.chunk_id) not in existing]
    if not to_embed:
        return

    embeddings = embed_texts([ch.chunk_data.get('chunk_text') for ch in to_embed])

    for ch, emb in zip(to_embed, embeddings): #emb is  List[float]
        _upsert_chunk(session, ch, emb)
       
    session.commit()

def retrieve_top_k(ask: RAGRequest, session: Session) -> List[Tuple[TranscriptChunk, float]]:
    query_vec = embed_texts([ask.question])[0]

    query = session.query(TranscriptChunk)

    if settings.USE_HYBRID_FTS: 
        sub_query = (session.query(EarningCallTranscript.id)
            .filter(EarningCallTranscript.raw_text_fts.op("@@")(ask.question))
            .limit(settings.FTS_CANDIDATE_LIMIT) 
            .subquery())
        query = query.filter(TranscriptChunk.transcript_id.in_(sub_query))
    
    query = query.filter(TranscriptChunk.embedding.isnot(None))

    if ask.company.year:
        query = query.filter(EarningCallTranscript.fiscal_year == ask.company.year)
    if ask.company.quarter:
        query = query.filter(EarningCallTranscript.fiscal_quarter == ask.company.quarter)
    if ask.company.company_name_query:
        resolved = resolve_company_to_ticker(ask.company) 
        query = query.join(EarningCallTranscript, TranscriptChunk.transcript_id == EarningCallTranscript.id)
        query = query.filter(or_(EarningCallTranscript.parent_company.has(name=resolved.name),
            EarningCallTranscript.parent_company.has(ticker=resolved.ticker)
            ))
    
    score = (1.0 - TranscriptChunk.embedding.cosine_distance(query_vec)).label("score")
    query = query.add_columns(score).order_by(score.desc()).limit(settings.TOP_K) 

    rows = query.all()

    return [(row[0], float(row[1])) for row in rows if float(row[1]) >= settings.MIN_SCORE]  




def augment(question: str, retrieved: List[Tuple[TranscriptChunk, float]]) -> Tuple[str, str]:
    context_blocks = []
    total_chars = 0
    for chunk, score in retrieved:
        if settings.CHUNK_STRATEGY == 'paragraph':
            header = (f"[chunk_id={chunk.chunk_id}, transcript_id={chunk.transcript_id} "
                      f" chunk_speaker={chunk.chunk_data.get('para_speaker')}, para_number={chunk.chunk_data.get('para_number')}, score={score:.3f}]")
        elif settings.CHUNK_STRATEGY == 'semantic':
            header = (f"[chunk_id={chunk.chunk_id}, transcript_id={chunk.transcript_id}, score={score:.3f}]")
            
        block = f"{header}\n{chunk.chunk_data.get('chunk_text')}"
        if total_chars + len(block) > settings.MAX_CONTEXT_CHARS: 
            break
        context_blocks.append(block)
        total_chars += len(block)

    system = (
        "You are an expert financial transcript assistant. "
        "Use the provided context. For answering"
        "If the context is insufficient, say: "
        "\"Not enough evidence in the transcripts to answer.\" "
        "Cite sources in brackets using chunk_id, e.g. [chunk_id=...]."
        "While citing a chunk, always use chunk's speaker name depicted by chunk_speaker if it is available . e.g. As said by (chunk_speaker)..."
    )

    user = (
        f"Question:\n{question}\n\n"
        f"Context:\n{chr(10).join(context_blocks)}\n\n"
        "Answer with citations after each claim."
    )
    return system, user

def ollama_chat(system: str, user: str) -> str:
    url = f"{settings.OLLAMA_BASE_URL}/api/chat" 
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=settings.REQUEST_TIMEOUT_SEC) 
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "").strip()

def openai_chat(system: str, user: str) -> str:
    url = f"{settings.OPENAI_BASE_URL}/chat/completions"  
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"} 
    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=settings.REQUEST_TIMEOUT_SEC) 
    try:
        err = resp.json()
        print("Error body:", json.dumps(err, indent=2))
    except Exception:
        print("Response body (text):", resp.text)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()

def generate_answer(question: str, retrieved: List[Tuple[TranscriptChunk, float]]) -> str:
    if not retrieved:
        return "Not enough evidence in the transcripts to answer."
    system, user = augment(question, retrieved)

    if settings.LLM_PROVIDER == "openai":
        return openai_chat(system, user)
    return ollama_chat(system, user)


def rag_response(answer: str, retrieved: List[Tuple[TranscriptChunk, float]]) -> RAGResponse:
    sources = []
    if settings.CHUNK_STRATEGY == "paragraph":
        for ch, score in retrieved:
                sources.append(
                    Sources(
                        company_id=ch.company_id,
                        transcript_id=ch.transcript_id,
                        chunk_id=ch.chunk_id,
                        speaker=ch.chunk_data.get('para_speaker'),
                        paragraph_num=ch.chunk_data.get('para_number'),
                        score=score,
                        snippet=ch.chunk_data.get('chunk_text')[:20],
                    )
                )
    elif  settings.CHUNK_STRATEGY == "semantic":
        for ch, score in retrieved:
            sources.append(
                Sources(
                    company_id=ch.company_id,
                    transcript_id=ch.transcript_id,
                    chunk_id=ch.chunk_id,
                    speaker="Multi",
                    paragraph_num=0,
                    score=score,
                    snippet=ch.chunk_data.get('chunk_text')[:20],
                )
            )
    return RAGResponse(answer=answer, sources=sources)