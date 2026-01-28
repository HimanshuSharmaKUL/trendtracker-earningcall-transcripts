import os
import sys
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)  # ensure backend package imports resolve

_DEFAULT_ENV = {
    "APP_NAME": "TrendTracker-Test",
    "DB_USER": "postgres_test",
    "DB_PASSWORD": "postgrestest_pw",
    "DB_NAME": "trendtracker_db_test",
    "DB_HOST": "localhost",
    "DB_PORT": "5434", # local port 5434 for test, 5433 for dev, 5432 previous local installation
    "CORS_ORIGINS": "http://localhost",
    "SPACY_MODEL": "en_core_web_sm",
    "OPENFIGI_API_BASE_URL": "https://api.fakeopenfigi.com",
    "OPENFIGI_API_KEY": "test_key",
    "CHUNK_STRATEGY": "paragraph",
    "EMBEDDING_MODEL": "all-MiniLM-L6-v2",
    "USE_HYBRID_FTS": "false",
    "FTS_CANDIDATE_LIMIT": "10",
    "TOP_K": "3",
    "MIN_SCORE": "0.5",
    "MAX_CONTEXT_CHARS": "3000",
    "CHUNK_SIZE": "200",
    "SEMENTIC_THRESH": "0.6",
    "REQUEST_TIMEOUT_SEC": "5",
    "LLM_PROVIDER": "ollama",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "llama3",
    "OPENAI_BASE_URL": "https://api.openai.com/v1",
    "OPENAI_MODEL": "gpt-4o-mini",
    "OPENAI_API_KEY": "test_key",
}

for key, value in _DEFAULT_ENV.items():
    os.environ.setdefault(key, value)


def _build_test_db_url() -> str:
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        return test_url

    db_user = os.environ.get("DB_USER", "postgres")
    db_password = os.environ.get("DB_PASSWORD", "postgres")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "trendtracker_db")
    if not db_name.endswith("_test"):
        db_name = f"{db_name}_test"
        os.environ["DB_NAME"] = db_name
    return f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


TEST_DATABASE_URL = _build_test_db_url()
if "TEST_DATABASE_URL" not in os.environ and "_test" not in TEST_DATABASE_URL:
    raise RuntimeError(
        "Refusing to run tests against a non-test database. "
        "Set TEST_DATABASE_URL or use a DB_NAME that ends with '_test'."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from backend.config import config as config_module

config_module.get_settings.cache_clear()

from backend.config.database import Base, get_session
from backend.main import create_application
from backend.models.companies_transcripts import Company, EarningCallTranscript

TEST_COMPANY_NAME = "Microsoft"
TEST_TICKER = "MSFT"
TEST_YEAR = 2025
TEST_QUARTER = 3


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = SessionLocal()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def app(test_session):
    app = create_application()

    def _override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = _override_get_session
    return app


@pytest.fixture(scope="function")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="function")
def mock_company(test_session):
    company = Company(
        name=TEST_COMPANY_NAME,
        ticker=TEST_TICKER,
        exchange_code="US",
        security_type="Common Stock",
        market_sector="Equity",
    )
    test_session.add(company)
    test_session.flush()
    return company


@pytest.fixture(scope="function")
def mock_transcript(test_session, mock_company):
    now = datetime.now(timezone.utc)
    transcript = EarningCallTranscript(
        company_id=mock_company.id,
        source="test",
        source_url="https://example.com",
        fiscal_year=TEST_YEAR,
        fiscal_quarter=TEST_QUARTER,
        fetched_at=now,
        preprocessed_at=now,
        updated_at=now,
        raw_text="Microsoft reported strong cloud revenue growth in Q3 2025.",
        para_structured_text=[
            {
                "paragraph_number": 1,
                "content": "Microsoft reported strong cloud revenue growth in Q3 2025.",
                "speaker": "CEO",
            }
        ],
        org_data={"org_unique_count": 1, "org_freq_count_sorted": [{"name": "microsoft", "count": 1}]},
        document_meta_data={"char_count": 0, "word_count": 0, "sentence_count": 0},
        content_hash="msft-q3-2025-test",
    )
    test_session.add(transcript)
    test_session.flush()
    return transcript
