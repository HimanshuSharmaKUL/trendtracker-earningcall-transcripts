# TrendTracker Coding Assignment: Earnings Call Transcripts RAG based Q&A

This repo is my submition towards TrendTracker coding assignment where my task was to make a web app for financial transcript ingestion, search, and RAG-based Q&A using FastAPI, PostgreSQL, and a simple Angular UI.

## Engineering Choices:

1. Use of transformer based spaCy model `en_core_web_trf` for NLP preprocessing
    - It is a heavy model which is expensive to load but it gives good Named-Entity Recognition
    - To manage its expensive loading, I only load it locally when preprocessing of transcripts is being done and not globally.

2. Uniqueness of the chunks

    - Avoiding chunk duplication was challanging.
    - There were some common chunks like 'Thank you for the call...', or 'Thank you for being present..' etc. which usually came in the first position of the paragraph chunks and were genrating UUID conflict. So to manage it I adopted several deduplication tricks:
        - I made a globally unique chunk hash using its parent transcript_id, its local index and its text,
        - I used Upserting - where I checked if the row exists for a given unique combination of `transcript_id` and `chunk_id` in the TranscriptChunk table.
        - Then I also did deduplication of the chunks and tried to fill only the unseen chunks.

3. Using 4-bit quantised model`gemma3:4b-it-q4_K_M`:

      - To generate augmented answers locally on my laptop, I used a light weight but accurate 4-bit quantised version of gemma3:4b, which which significantly reduces the VRAM requirement in GPU.

4. Trying to send less UUIDs to frontend in backend responsees because frontend can not do anything with them apart from making another backend calls

## Explanations and Descriptions

### Transcript Data Source & Ingestion Approach

- User provides data in the `IngestRequest` format, which includes a free form company query, year, quarter, security type (default is 'Common Stock'), exchange code (default is 'US')
- Company resolution: This free-form company input is resolved to a ticker using OpenFIGI API.
- Transcript is sourced: Then **DefeatBeta API** retrieves earnings-call transcripts. It sources from database hosted on huggingface https://huggingface.co/datasets/bwzheng2010/yahoo-finance-data
- **Preprocessing**:
  - I construct raw text from the ingested transcripts
  - Then ORG named-entities are extracted via spaCy (see NLP section).
  - Then some metadata (char/word/sentence counts) and a SHA-256 `content_hash` is computed.
- **Persistence**:
  - Here, just before persisting transcript record, I create or reuse a company record.
  - Then I insert transcript into `transcripts` table.
  - It then inserts per-ORG counts into `orgs_in_transcripts`.
  - Unique constraints on the `EarningCallTranscript` table to prevent duplicate transcripts by company/period and content hash.

### NLP Approach for Organization Extraction

- I use spaCy model defined by `SPACY_MODEL` (I use `.env.example` is `en_core_web_trf`).
- It extracts named `ORG` entities from the full transcript text.
- It normalizes the org names (lowercase, trimmed) and counts their mentions.
- Then it is Stored:
  - Data about extracted organisations - `org_data` summary (unique count + frequency list).
  - Raw org counts into `orgs_in_transcripts` for queryability.

### Full-Text Search Implementation

- There is a PostgreSQL computed column in the `EarningCallTranscript` table: `raw_text_fts` which is computed from `to_tsvector('english', raw_text)` by postgres itself.
- I use GIN index on `raw_text_fts` for fast query execution.
- Query path:
  - Uses `websearch_to_tsquery` for Google-like syntax.
  - It tries to rank results with `ts_rank_cd`.
  - Then it generates highlighted snippets contained in the raw text with `ts_headline`.
- Filters supported: `company_id`, `fiscal_year`, `fiscal_quarter`, plus pagination.

### RAG Approach & Grounding Strategy

- For Chunking, there are two options to choose from:
  - `paragraph`: splits by paragraph and chunks to a max size controlled by environment variable `CHUNK_SIZE`
  - `semantic`: sentence-level similarity chunking with threshold also controlled by env variable `SEMENTIC_THRESH`
- Then for Embeddings, the chunks are converted into embeddings using SentenceTransformer model - `all-MiniLM-L6-v2` (env variable `EMBEDDING_MODEL`), it outputs 384-dim vectors and then embeddings are stored in pgvector enabled PostgreSQL in the column called `transcript_chunks.embedding`.
- Then while Retrieving, I retrieve the top K vectors (also an environment variable)
  - I calculate cosine distance between the query and the stored chunk embeddings.
  - There is also aptional hybrid filter using full tesxt search of PostgreSQL, this uses `USE_HYBRID_FTS` and `FTS_CANDIDATE_LIMIT` variables.
- Grounding in transcripts:
  - The system prompt is augmented with top-k chunks (bounded by `MAX_CONTEXT_CHARS`) along with chunk meta data like who was the speaker, which paragraph does it belong to etc.
  - Answer includes citations in `[chunk_id=...]` format which are highlighted on the frontend.
  - If no strong evidence, responds: **"Not enough evidence in the transcripts to answer."** This usually happens when the minimum score to match the query with the chunks is very high (controlled by `MIN_SCORE` variable). I have observed this threshold should not be too high. A value above 0.4, 0.45 gives good results.
- **LLM Provider**: We can choose `openai` or `ollama` chosen via `LLM_PROVIDER`. OpenAI required `OPENAI_API_KEY` and we can choose our model. I ran this in my local system using Ollama and I used `gemma3:4b-it-q4_K_M` which is 4-bit quantised version of gemma3:4b, which which significantly reduces the VRAM requirement in GPU.

## API Endpoints

Base app: `backend/main.py`
Ingestion: `POST /ingest/ingest-in`
Search: `POST /search/query`
Rag based Q&A: `POST /qna/ask`

## Frontend

Single-page Angular console (`frontend/src/app/*`) with:

- **Ingest** form calls `/ingest/ingest-in`
- **Search** panel calls `/search/query`
- **Q&A** panel calls `/qna/ask` with inline citation rendering

---

## How to Run Locally

### 1) Start PostgreSQL and alembic migrations
From the root do
```bash
docker compose -f docker-compose.trendtrackerhimanshu.yml up -d
```
Then run alembic migrations
```bash
alembic upgrade head
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
- Make python virtual env: `python -m venv .venv`
- Activate the python environment by running: `.venv\Scripts\activate`
- Install dependencies: `pip install requirements.txt`
- Download the spaCy model: `python -m spacy download en_core_web_trf`
- Run API:
  ```
  python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
  ```

### 4) Frontend
To run the frontend
```
cd frontend
npm install
npm start
```

We'll have frontend at `http://localhost:4200` and FastAPI backend at `http://localhost:8000`.
     min score threshold, “not enough evidence” response, source formatting
7. **API contracts (3 cases)**
   - /ingest input validation, /search validation, /qna validation

Total: **34 core backend test cases** across unit + service + API contract layers.
