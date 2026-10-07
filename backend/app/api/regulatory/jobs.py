import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.regulatory.ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/ingest")
async def run_full_ingestion(db: AsyncSession = Depends(get_db)):
    from app.regulatory.adapters.ecfr import ECFRAdapter
    from app.regulatory.adapters.federal_register import FederalRegisterAdapter
    from app.regulatory.adapters.iac import IACAdapter
    from app.regulatory.adapters.iurc_rulemakings import IURCRulemakerAdapter
    from app.regulatory.adapters.iurc_gaos import IURCGAOAdapter
    from app.regulatory.adapters.iurc_investigations import IURCInvestigationsAdapter
    from app.regulatory.adapters.idem_rulemakings import IDEMRulemakerAdapter

    results = {}

    for adapter_class, name in [
        (ECFRAdapter, "ecfr"),
        (FederalRegisterAdapter, "federal_register"),
        (IACAdapter, "iac"),
        (IURCRulemakerAdapter, "iurc_rulemakings"),
        (IURCGAOAdapter, "iurc_gaos"),
        (IURCInvestigationsAdapter, "iurc_investigations"),
        (IDEMRulemakerAdapter, "idem_rulemakings"),
    ]:
        try:
            adapter = adapter_class()
            if not await adapter.health_check():
                logger.warning("Health check failed for %s — skipping ingestion", name)
                results[name] = {
                    "status": "skipped",
                    "new": 0,
                    "changed": 0,
                    "unchanged": 0,
                    "skipped": 0,
                    "errors": 0,
                    "health_check": "failed",
                }
                continue
            summary = await run_ingestion(adapter, db)
            results[name] = {"status": "ok", **summary}
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}

    return results


ADAPTER_MAP = {
    "ecfr": "ECFRAdapter",
    "federal_register": "FederalRegisterAdapter",
    "iac": "IACAdapter",
    "iurc_rulemakings": "IURCRulemakerAdapter",
    "iurc_gaos": "IURCGAOAdapter",
    "iurc_investigations": "IURCInvestigationsAdapter",
    "idem_rulemakings": "IDEMRulemakerAdapter",
}

_ADAPTER_IMPORTS = {
    "ecfr": ("app.regulatory.adapters.ecfr", "ECFRAdapter"),
    "federal_register": ("app.regulatory.adapters.federal_register", "FederalRegisterAdapter"),
    "iac": ("app.regulatory.adapters.iac", "IACAdapter"),
    "iurc_rulemakings": ("app.regulatory.adapters.iurc_rulemakings", "IURCRulemakerAdapter"),
    "iurc_gaos": ("app.regulatory.adapters.iurc_gaos", "IURCGAOAdapter"),
    "iurc_investigations": ("app.regulatory.adapters.iurc_investigations", "IURCInvestigationsAdapter"),
    "idem_rulemakings": ("app.regulatory.adapters.idem_rulemakings", "IDEMRulemakerAdapter"),
}


@router.post("/ingest/{source_system}")
async def run_single_ingestion(source_system: str, db: AsyncSession = Depends(get_db)):
    if source_system not in ADAPTER_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source_system '{source_system}'. Must be one of: {', '.join(ADAPTER_MAP.keys())}",
        )

    module_path, class_name = _ADAPTER_IMPORTS[source_system]
    import importlib
    module = importlib.import_module(module_path)
    adapter_class = getattr(module, class_name)

    try:
        adapter = adapter_class()
        if not await adapter.health_check():
            logger.warning("Health check failed for %s — skipping ingestion", source_system)
            return {
                "status": "skipped",
                "new": 0,
                "changed": 0,
                "unchanged": 0,
                "skipped": 0,
                "errors": 0,
                "health_check": "failed",
            }
        summary = await run_ingestion(adapter, db)
        return {"status": "ok", **summary}
    except Exception as e:
        return {"status": "error", "error": str(e)}
