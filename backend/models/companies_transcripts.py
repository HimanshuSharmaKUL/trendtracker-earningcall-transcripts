import uuid
from sqlalchemy import Column, Text, Integer, ForeignKey, DateTime, UniqueConstraint, Index, Computed
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from backend.config.database import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy.sql import func



class Company(Base):
    __tablename__ = "companies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    ticker = Column(Text, nullable=False, unique=True) #ticker must be unique
    exchange_code = Column(Text, nullable=False)
    security_type = Column(Text, nullable=False)
    market_sector = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    transcripts = relationship("EarningCallTranscript", back_populates="parent_company")#one company - many transcripts

    __table_args__ = (
        UniqueConstraint("ticker", "exchange_code", name="uq_company_ticker_exchange"),
    )

class EarningCallTranscript(Base):
    __tablename__ = "transcripts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    # company_input = Column(Text, nullable=False)
    source = Column(Text, nullable=False)
    source_url = Column(Text, nullable=True)
    fiscal_year = Column(Integer, nullable=True)
    fiscal_quarter = Column(Integer, nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    preprocessed_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    raw_text = Column(Text, nullable=False)
    para_structured_text =  Column(JSONB, nullable=False, default=dict) #<- Fix this : it is a list of dicts 
    org_data = Column(JSONB, nullable=False, default=dict)
    document_meta_data = Column(JSONB, nullable=False, default=dict)
    content_hash = Column(Text, nullable=False)
    # spacy_doc = 
    raw_text_fts = Column(TSVECTOR, Computed("to_tsvector('english', coalesce(raw_text, ''))", persisted=True))  # fill on db side
    
    parent_company = relationship("Company", back_populates="transcripts") #many transcripts can have 1 company
    org_entities = relationship("TranscriptOrgEntity", back_populates="transcript_org")
    chunks = relationship("TranscriptChunk", back_populates="parent_transcript")

    __table_args__ = (
      UniqueConstraint("company_id", "fiscal_year", "fiscal_quarter", name="uq_transcripts_period"), #one transcript per company for 1 fiscal year and 1 fiscal quarter
      UniqueConstraint("company_id", "content_hash", name="uq_transcripts_hash"),
      # Index("ix_transcripts_company_time", "company_id", "call_timestamp"), #<-- fix this
      Index("ix_transcripts_fts", "raw_text_fts", postgresql_using="gin"),
    )

class TranscriptOrgEntity(Base):
    __tablename__ = "orgs_in_transcripts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id = Column(UUID(as_uuid=True), ForeignKey("transcripts.id"), nullable=False)
    org_name = Column(Text, nullable=False)
    mention_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True))

    transcript_org = relationship("EarningCallTranscript", back_populates="org_entities")

    __table_args__ = (
        Index("ix_org_transcript", "transcript_id"), #lookup of all orgs in a transcript
        Index("ix_org_norm", "org_name"), #reverse lookup - which transcripts mention X
        UniqueConstraint("transcript_id", "org_name", name="uq_org_per_transcript"),
    )

class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id = Column(UUID(as_uuid=True), ForeignKey("transcripts.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_hash = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Vector(384), nullable=True)  #must match with RAG_EMB_DIM
    embedding_model = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True))
    chunk_data = Column(JSONB, nullable=False, default=dict)

    parent_transcript = relationship("EarningCallTranscript", back_populates="chunks")

    __table_args__ = (
      UniqueConstraint("transcript_id", "chunk_id", name="uq_chunk_id"),
      Index("ix_chunk_transcript", "transcript_id"),
      Index("ix_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"}
            ),
    )