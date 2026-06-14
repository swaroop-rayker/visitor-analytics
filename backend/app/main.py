import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import analytics, auth, system, tracking
from app.config import settings
from app.services.maintenance import retention_loop

logger = logging.getLogger("visitor_analytics")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_production()
    task = asyncio.create_task(retention_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Private Visitor Analytics API",
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", settings.public_base_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Invalid request", "errors": exc.errors()})


@app.exception_handler(SQLAlchemyError)
async def database_error(_request: Request, exc: SQLAlchemyError):
    logger.exception("Database operation failed", exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "Storage temporarily unavailable"})


@app.exception_handler(Exception)
async def unhandled_error(_request: Request, exc: Exception):
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error"})


app.include_router(tracking.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok"}
