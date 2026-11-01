from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.config import settings
from app.api.regulatory.regulations import router as regulations_router
from app.api.regulatory.actions import router as actions_router
from app.api.regulatory.diff import router as diff_router
from app.api.regulatory.timeline import router as timeline_router
from app.api.regulatory.impact import router as impact_router
from app.api.regulatory.search import router as search_router
from app.api.regulatory.jobs import router as jobs_router
from app.api.engine.routes import router as engine_router
from app.api.company.routes import router as company_router
from app.api.company.org import router as company_org_router
from app.api.company.versions import router as company_versions_router
from app.api.company.upload import router as company_upload_router
from app.api.company.doc_admin import router as company_doc_admin_router
from app.company_ingest.jobs import startup_sweep


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Reclaim ingest jobs orphaned by a restart (TDD §6.2). Never raises.
    await startup_sweep()
    yield


app = FastAPI(title="Strata API", lifespan=_lifespan)

# Only the configured frontend origin(s) may call the API. Trailing slashes are ignored.
_cors = [o.strip().rstrip("/") for o in settings.FRONTEND_URL.split(",") if o.strip()]
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
app.include_router(company_org_router)
app.include_router(company_versions_router)
app.include_router(company_upload_router)
app.include_router(company_doc_admin_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
