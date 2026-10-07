from fastapi import FastAPI
from app.api.regulatory.regulations import router as regulations_router
from app.api.regulatory.actions import router as actions_router
from app.api.regulatory.diff import router as diff_router
from app.api.regulatory.timeline import router as timeline_router
from app.api.regulatory.impact import router as impact_router
from app.api.regulatory.search import router as search_router
from app.api.regulatory.jobs import router as jobs_router

app = FastAPI(title="Strata API")

app.include_router(regulations_router)
app.include_router(actions_router)
app.include_router(diff_router)
app.include_router(timeline_router)
app.include_router(impact_router)
app.include_router(search_router)
app.include_router(jobs_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
