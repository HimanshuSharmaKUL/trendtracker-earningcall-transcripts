
from datetime import datetime, timezone
import uuid

from backend.RequestSchemas.qa import IngestRequest
from backend.RequestSchemas.qa import RAGRequest
from backend.models.companies_transcripts import EarningCallTranscript, TranscriptChunk
from backend.services.InternalSchemas.chunk import Chunk
from backend.services.rag import embed_chunks, generate_answer, retrieve_top_k


def _unit_vec(index, dim=384):
    vec = [0.0] * dim
    vec[index] = 1.0
    return vec

def _build_transcript(company_id, raw_text):
    now = datetime.now(timezone.utc)
    return EarningCallTranscript(
        id=uuid.uuid4(),
        company_id=company_id,
        source="test",
        source_url="https://schopenhauer.com",
        fiscal_year=2024,
        fiscal_quarter=4,
        fetched_at=now,
        preprocessed_at=now,
        updated_at=now,
        raw_text=raw_text,
        para_structured_text=[{"paragraph_number": 1, "content": raw_text, "speaker": "CEO"}],
        org_data={"org_unique_count": 0, "org_freq_count_sorted": []},
        document_meta_data={"char_count": len(raw_text), "word_count": 0, "sentence_count": 0},
        content_hash=uuid.uuid4().hex,
    )


def test_embed_chunks_upserts_embedding(monkeypatch, test_session, mock_company):
    #create transcript row to satisfy FK for TranscriptChunk.
    transcript = _build_transcript(mock_company.id, "Some transcript text.")
    test_session.add(transcript)
    test_session.flush()

    chunk_id = uuid.uuid4()
    chunk = Chunk(
        transcript_id=transcript.id,
        company_id=mock_company.id,
        chunk_id=chunk_id,
        chunk_hash="hash-1",
        chunk_index=0,
        chunk_data={"chunk_text": "Some transcript text."},
    )

    #Artificially pre-insert row with embedding=None to exercise the upsert path.
    pre = TranscriptChunk(
        transcript_id=transcript.id,
        company_id=mock_company.id,
        chunk_id=chunk_id,
        chunk_hash="hash-1",
        chunk_index=0,
        embedding=None,
        embedding_model='huggingface',
        updated_at=None,
        chunk_data={"chunk_text": "Some transcript text."},
    )
    test_session.add(pre)
    test_session.flush()

    monkeypatch.setattr(
        "backend.services.rag.embed_texts",
        lambda texts: [_unit_vec(0)],
    )

    embed_chunks([chunk], test_session)

    refreshed = (
        test_session.query(TranscriptChunk)
        .filter(TranscriptChunk.transcript_id == transcript.id)
        .filter(TranscriptChunk.chunk_id == chunk_id)
        .one()
    )
    assert refreshed.embedding is not None
    assert refreshed.embedding_model is not None


def test_retrieve_top_k_returns_best_match(monkeypatch, test_session, mock_company):
    transcript = _build_transcript(mock_company.id, "Revenue grew in Q4.")
    test_session.add(transcript)
    test_session.flush()

    emb_a = _unit_vec(0)
    emb_b = _unit_vec(1)

    chunk_a = TranscriptChunk(
        transcript_id=transcript.id,
        company_id=mock_company.id,
        chunk_id=uuid.uuid4(),
        chunk_hash="hash-a",
        chunk_index=0,
        embedding=emb_a,
        embedding_model="test",
        updated_at=datetime.now(timezone.utc),
        chunk_data={"chunk_text": "Revenue grew strongly."},
    )
    chunk_b = TranscriptChunk(
        transcript_id=transcript.id,
        company_id=mock_company.id,
        chunk_id=uuid.uuid4(),
        chunk_hash="hash-b",
        chunk_index=1,
        embedding=emb_b,
        embedding_model="test",
        updated_at=datetime.now(timezone.utc),
        chunk_data={"chunk_text": "Unrelated topic."},
    )
    test_session.add_all([chunk_a, chunk_b])
    test_session.flush()

    #ake the query vector match emb_a exactly.
    monkeypatch.setattr(
        "backend.services.rag.embed_texts",
        lambda texts: [emb_a],
    )

    # empty company_name_query to avoid resolver calls
    ask = RAGRequest(question="How did revenue grow?", company=IngestRequest(company_name_query="", year=2024, quarter=4))
    rows = retrieve_top_k(ask, test_session)

    assert len(rows) == 1  # MIN_SCORE=0.5 removes the orthogonal vector
    assert rows[0][0].chunk_id == chunk_a.chunk_id
    assert rows[0][1] >= 0.5


def test_generate_answer_not_enough_evidence():
    #No retrieved chunks
    #Can happen due to high similarity threshold
    answer = generate_answer("What happened?", [])
    assert answer == "Not enough evidence in the transcripts to answer."