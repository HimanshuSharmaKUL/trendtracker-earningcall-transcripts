from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json

from backend.config.config import get_settings
from backend.routes import ingest, quesans, search


settings = get_settings()

raw_origins = settings.CORS_ORIGINS
if isinstance(raw_origins, str):
    raw_origins = raw_origins.strip()
    if raw_origins.startswith("["):
        origins = json.loads(raw_origins)
    else:
        origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
else:
    origins = raw_origins
if not origins:
    raise RuntimeError("CORS_ORIGINS must be configured.")
origins = [o.rstrip("/") for o in origins]


def create_application():
    application = FastAPI(title="Trendtracker:Himanshu")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,  # CRITICAL for cookies: allows credentials (cookies) to be sent with requests
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Access-Control-Allow-Origin",
            "X-Requested-With",
            "X-User-Timezone",
        ],
        expose_headers=["*"],
    )

    application.include_router(ingest.ingest_router)
    application.include_router(search.search_router)
    application.include_router(quesans.qna_router)
    return application


app = create_application()


@app.get("/")
async def root():
    return {"message": "FastAPI app is running."}


@app.get("/__debug_cors_t")
def debug_cors():
    return {"origins": origins}