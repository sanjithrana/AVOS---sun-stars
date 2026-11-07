import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
from src.errors import (
    APIException,
    api_exception_handler,
    internal_exception_handler,
    validation_exception_handler,
)
from src.routes.agents import router as agents_router
from src.routes.assets import router as assets_router
from src.routes.events import router as events_router
from src.routes.gates import router as gates_router
from src.routes.gpu import router as gpu_router
from src.routes.downloads import router as downloads_router
from src.routes.jobs import router as jobs_router
from src.routes.models import router as models_router
from src.routes.settings import router as settings_router
from src.routes.projects import router as projects_router
from src.routes.shots import router as shots_router
from src.routes.temporal import router as temporal_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Solunex API")

# Browsers on this machine *or the local network* (opening the UI via
# http://192.168.x.y:3000) must be able to call the API. The previous
# fixed list only allowed localhost, so LAN access failed with CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, internal_exception_handler)

app.include_router(projects_router)
app.include_router(jobs_router)
app.include_router(gates_router)
app.include_router(agents_router)
app.include_router(events_router)
app.include_router(assets_router)
app.include_router(shots_router)
app.include_router(temporal_router)
app.include_router(models_router)
app.include_router(settings_router)
app.include_router(gpu_router)
app.include_router(downloads_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
