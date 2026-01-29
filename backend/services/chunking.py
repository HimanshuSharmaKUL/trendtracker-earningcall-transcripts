import hashlib
from typing import List
import uuid
from sqlalchemy.orm import Session
from backend.config.embeddings import get_semantic_model
import spacy
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from backend.RequestSchemas.qa import RAGRequest
from backend.RequestSchemas.qa import IngestRequest #IngestRequest from qa not ingest
from backend.config.config import get_settings
from backend.models.companies_transcripts import EarningCallTranscript
from backend.services.InternalSchemas.chunk import Chunk
from backend.services.fetch_transcripts import create_get_company
from backend.services.ticker_from_company import resolve_company_to_ticker

settings = get_settings()

def _fetch_transcripts(ask: IngestRequest, session: Session) -> List[EarningCallTranscript]:
    resolved = resolve_company_to_ticker(ask) #resolver takes input type IngestRequest
    company = create_get_company(resolved, session)

    q = session.query(EarningCallTranscript)
    if company:
        q = q.filter(EarningCallTranscript.company_id == company.id)
    if ask.year:
        q = q.filter(EarningCallTranscript.fiscal_year == ask.year)
    if ask.quarter:
        q = q.filter(EarningCallTranscript.fiscal_quarter == ask.quarter)
    return q.all()

# def paragraph_chunking(transcript: EarningCallTranscript) -> List[Chunk]:

def _chunk_hash(transcript_id: str, chunk_index: int, text: str) -> str:
    payload = f"{transcript_id}:{chunk_index}:{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

_CHUNK_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "trendtrackerHimanshu.transcript_chunk")
def _chunk_id_from_hash(hash_value: str) -> uuid.UUID:
    return uuid.uuid5(_CHUNK_NAMESPACE, hash_value)

def _chunk_text(text: str, chunk_size: int = 200) -> list:
    chunks = []
    current_chunk = ''
    words = text.split()
    for word in words:
        #check if adding the word exceeds chunk size
        if len(current_chunk) + len(word) + 1 <= chunk_size:
            current_chunk += word + ' ' #keep on adding the words to current_chunk untill you hit the chunk_size
        else:
            #store the current chunk and start new chunk
            chunks.append(current_chunk.strip())
            current_chunk = word + ' '
    #add the last chunk if not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def chunk_paras(transcript: EarningCallTranscript, chunk_size) -> List[Chunk]:
    all_chunks: List[Chunk] = []
    para_structured_text = transcript.para_structured_text
    idx = 0
    for para in para_structured_text:
        para_number = para.get("paragraph_number")
        para_text = para.get('content')
        para_speaker = para.get('speaker')
        chunks = _chunk_text(para_text, chunk_size=chunk_size)
        for i, chunk in enumerate(chunks):
            idx += 1
            ch_hash = _chunk_hash(str(transcript.id), idx, chunk)
            c_id = _chunk_id_from_hash(ch_hash)
            all_chunks.append(Chunk(
                transcript_id = transcript.id,
                company_id = transcript.company_id,
                chunk_id= c_id,
                chunk_hash= ch_hash,
                chunk_index= idx,
                chunk_data = {"para_number": para_number,
                "para_speaker": para_speaker,
                "para_chunk_index": i,
                "chunk_char_count": len(chunk),
                "chunk_word_count": len(chunk.split()),
                "chunk_token_count": len(chunk)/4, #rough token estimate
                "chunk_text": chunk}))
    return all_chunks


def _semantic_chunk_text(text: str, similarity_threshold: float = 0.8, max_tokens: int = 500) -> list:
    """ Splits text into semantic chunks based on sentence similarity and max token length."""
    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents]
    if not sentences:
        return []

    embeddings = get_semantic_model()
    chunks = []
    current_chunk = [sentences[0]]
    current_embedding = embeddings[0]

    for i in range(1, len(sentences)):
        sim = cosine_similarity([current_embedding], [embeddings[i]])[0][0]
        chunk_token_count = len(" ".join(current_chunk)) // 4

        #we append the sentences into the chunk untill the sim is > threshold
        if sim >= similarity_threshold and chunk_token_count < max_tokens:
            current_chunk.append(sentences[i])
            current_embedding = np.mean([current_embedding, embeddings[i]], axis=0)
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentences[i]]
            current_embedding = embeddings[i]
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def semantic_chunk(transcript: EarningCallTranscript, similarity_threshold: float = 0.6, max_tokens: int = 500) -> list[dict]:
    """Takes PDF pages with text and splits them into semantic chunks."""
    all_chunks: List[Chunk] = []
    text = transcript.raw_text
    chunks = _semantic_chunk_text(text, similarity_threshold=similarity_threshold, max_tokens=max_tokens)
    for i, chunk in enumerate(chunks):
        ch_hash = _chunk_hash(str(transcript.id), i, chunk)
        c_id = _chunk_id_from_hash(ch_hash)
        all_chunks.append(Chunk(
            transcript_id=transcript.id,
            company_id=transcript.company_id,
            chunk_id=c_id,
            chunk_hash=ch_hash,
            chunk_index=i,
            chunk_data={#"page_number": page_number,
                    "chunk_index": i,
                    "chunk_char_count": len(chunk),
                    "chunk_word_count": len(chunk.split()),
                    "chunk_token_count": len(chunk) / 4, #rough token estimate
                    "chunk_text": chunk}))
    return all_chunks

def build_chunks(ask: IngestRequest, session: Session) -> List[Chunk]:
    transcripts = _fetch_transcripts(ask, session)
    
    all_chunks: List[Chunk] = []
    for t in transcripts:
        if settings.CHUNK_STRATEGY == "paragraph":
            chunks = chunk_paras(t, chunk_size=settings.CHUNK_SIZE)
        elif settings.CHUNK_STRATEGY == 'semantic':
            chunks = semantic_chunk(t, similarity_threshold=settings.SEMENTIC_THRESH) 
        all_chunks.extend(chunks)
    return all_chunks

