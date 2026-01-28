# TrendTracker: Earnings Call Transcripts RAG based Q&A

Financial transcript ingestion, search, and RAG-based Q&A built on FastAPI, PostgreSQL (FTS + pgvector), and a simple Angular UI.

### Backend: Transcript Data Source & Ingestion Approach

- User provides data in the `IngestRequest` format which is a free form company query, year, quarter, security type, exchange code (US, UK etc.)
- Company resolution: This free-form company input is resolved to a ticker using **OpenFIGI** API.
- Transcript is sourced: Then **DefeatBeta API** retrieves earnings-call transcripts. It sources from database hosted on huggingface https://huggingface.co/datasets/bwzheng2010/yahoo-finance-data
- **Preprocessing**:
  - Concatenates transcript paragraphs into `raw_text`.
  - Extracts ORG entities via spaCy (see NLP section).
  - Computes metadata (char/word/sentence counts) and a SHA-256 `content_hash`.
- **Persistence**:
  - Creates or reuses a company record.
  - Inserts transcript into `transcripts` table.
  - Inserts per-ORG counts into `orgs_in_transcripts`.
  - Unique constraints prevent duplicate transcripts by company/period and content hash.

### Backend: NLP Approach for Organization Extraction

- Uses spaCy model defined by `SPACY_MODEL` (default in `.env.example` is `en_core_web_trf`).
- Extracts `ORG` entities from the full transcript text.
- Normalizes org names (lowercase, trimmed) and counts mentions.
- Stores:
  - `org_data` summary (unique count + frequency list).
  - Raw org counts into `orgs_in_transcripts` for queryability.

### Full-Text Search Implementation

- PostgreSQL computed column: `raw_text_fts` = `to_tsvector('english', raw_text)`.
- GIN index on `raw_text_fts` for fast query execution.
- Query path:
  - Uses `websearch_to_tsquery` for Google-like syntax.
  - Ranks results with `ts_rank_cd`.
  - Generates highlighted snippets with `ts_headline`.
- Filters supported: `company_id`, `fiscal_year`, `fiscal_quarter`, plus pagination.

### RAG Approach & Grounding Strategy

- **Chunking**: There are two options to choose from:
  - `paragraph`: splits by paragraph and chunks to a max size controlled by environment variable `CHUNK_SIZE`
  - `semantic`: sentence-level similarity chunking with threshold also controlled by env variable `SEMENTIC_THRESH`
- **Embeddings**: The chunks converted into embeddings using SentenceTransformer model `EMBEDDING_MODEL`, default 384-dim and stored in pgvector enabled PostgreSQL in the column called `transcript_chunks.embedding`.
- **Retrieval**: THen while retrieving, I retrieve the top K vectors (also an environment variable)
  - I calculate cosine distance between the query and the stored chunk embeddings.
  - There is also aptional hybrid filter using full tesxt search of PostgreSQL, this uses `USE_HYBRID_FTS` and `FTS_CANDIDATE_LIMIT` variables.
- **Grounding**:
  - The system prompt is augmented with top-k chunks (bounded by `MAX_CONTEXT_CHARS`) along with chunk meta data like who was the speaker, which paragraph does it belong to etc.
  - Answer includes citations in `[chunk_id=...]` format which are highlighted on the frontend.
  - If no strong evidence, responds: **"Not enough evidence in the transcripts to answer."** This usually happens when the minimum score to match the query with the chunks is very high (controlled by `MIN_SCORE` variable). I have observed this threshold should not be too high. A value above 0.4, 0.45 gives good results.
- **LLM Provider**: We can choose `openai` or `ollama` chosen via `LLM_PROVIDER`. OpenAI required `OPENAI_API_KEY` and we can choose our model. I ran this in my local system using Ollama and I used `gemma3:4b-it-q4_K_M` which is 4-bit quantised version of gemma3:4b, which which significantly reduces the VRAM requirement in GPU.

---

## API Endpoints

Base app: `backend/main.py`
Ingestion: `POST /ingest/ingest-in`
Search: `POST /search/query`
Rag based Q&A: `POST /qna/ask`

## Frontend

Single-page Angular console (`frontend/src/app/app.component.*`) with:

- **Ingest** form calls `/ingest/ingest-in`
- **Search** panel calls `/search/query`
- **Q&A** panel calls `/qna/ask` with inline citation rendering

The frontend allows overriding the API base URL, which must be included in `CORS_ORIGINS`.

---

## How to Run Locally

### 1) Start PostgreSQL + pgvector

```bash
docker compose -f docker-compose.trendtrackerhimanshu.yml up -d
```

This starts:

- Databse on Postgres on `localhost:5433`
- Visualiser on pgAdmin on `localhost:5050`

### 2) Configure environment

Copy the template ` .env.example` and fill in secrets:
We must set:

- `OPENFIGI_API_KEY` for ticker resolution. This API Key is free to obtain. As OpenFIGI is an oopen standard unique identifier of financial instruments.
- `LLM_PROVIDER` and corresponding OpenAI and Ollama settings
- `CORS_ORIGINS` to include the frontend URL

### 3) Backend

- Python version: **3.12.3** (from `.python-version`)
- Install dependencies: `pip install requirements.txt`
  - Key libs: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2`, `pgvector`,
    `defeatbeta_api`, `spacy`, `sentence-transformers`, `scikit-learn`, `pandas`, `numpy`
- Download the spaCy model:
  ```
  python -m spacy download en_core_web_trf
  ```
- Run API:
  ```
  python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
  ```

### 4) Frontend

```
cd frontend
npm install
npm start
```

Open `http://localhost:4200` and point the API base URL to `http://localhost:8000`.

## Backend Testing Guide (what to implement)

Only the **number and types** of tests/cases to cover core logic:

1. **Ticker resolution (4 cases)**
   - success, empty match (404), auth error, upstream 4xx/5xx handling
2. **Ingestion pipeline (6 cases)**
   - new company, existing company reuse, transcript not found, duplicate transcript (409),
     empty transcript data, persistence of org counts
3. **Preprocessing/NLP (4 cases)**
   - ORG extraction count, metadata computation, content hash stability, normalization
4. **FTS search (5 cases)**
   - rank ordering, snippet highlight, filter by company/year/quarter, pagination, no hits
5. **Chunking (6 cases)**
   - paragraph chunk sizing, semantic chunk thresholding, chunk hash uniqueness,
     token/count metadata, empty transcript guard, multi-transcript aggregation
6. **RAG retrieval + response (6 cases)**
   - embedding upsert, retrieval top-k size, hybrid FTS gating,
     min score threshold, “not enough evidence” response, source formatting
7. **API contracts (3 cases)**
   - /ingest input validation, /search validation, /qna validation

Total: **34 core backend test cases** across unit + service + API contract layers.
