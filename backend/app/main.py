import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.api.regulatory.regulations import router as regulations_router
from app.api.regulatory.actions import router as actions_router
from app.api.regulatory.diff import router as diff_router
from app.api.regulatory.timeline import router as timeline_router
from app.api.regulatory.impact import router as impact_router
from app.api.regulatory.search import router as search_router
from app.api.regulatory.jobs import router as jobs_router
from app.api.engine.routes import router as engine_router
from app.api.company.routes import router as company_router

app = FastAPI(title="Strata API")

_cors = [o.strip() for o in os.getenv("ENGINE_CORS_ORIGINS", "*").split(",") if o.strip()]
if "*" not in _cors:
    _cors.append("http://localhost:3000")
app.add_middleware(CORSMiddleware, allow_origins=_cors, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(regulations_router)
app.include_router(actions_router)
app.include_router(diff_router)
app.include_router(timeline_router)
app.include_router(impact_router)
app.include_router(search_router)
app.include_router(jobs_router)
app.include_router(engine_router)
app.include_router(company_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
