"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas import (
    LinkAnalysisRequest,
    LinkAnalysisResponse,
    ErrorResponse
)
from app.services.analysis_service import AnalysisService
from app.services.website_extractor import WebsiteExtractionException
from app.utils.validators import ValidationError, SSRFProtectionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("link_analysis_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Initializing AI-Powered Website Link Analysis API...")
    logger.info(f"Environment: {settings.ENVIRONMENT} | LLM Provider: {settings.LLM_PROVIDER}")
    # Pre-instantiate service
    app.state.analysis_service = AnalysisService()
    yield
    logger.info("Shutting down Website Link Analysis API...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-grade FastAPI service that extracts and analyzes website content using LLMs "
        "to deliver business, competitor, SEO, search query, and audience intelligence."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Exception Handlers
# --------------------------------------------------------------------------

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle custom URL validation failures."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            success=False,
            error="Invalid URL",
            detail=str(exc)
        ).model_dump()
    )


@app.exception_handler(SSRFProtectionError)
async def ssrf_error_handler(request: Request, exc: SSRFProtectionError):
    """Handle SSRF security blocks."""
    logger.warning(f"Blocked SSRF attempt: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=ErrorResponse(
            success=False,
            error="Security Access Denied (SSRF Protection)",
            detail=str(exc)
        ).model_dump()
    )


@app.exception_handler(WebsiteExtractionException)
async def extraction_error_handler(request: Request, exc: WebsiteExtractionException):
    """Handle website scraping / connectivity errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error="Website Inaccessible",
            detail=exc.message
        ).model_dump()
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI / Pydantic schema validation errors."""
    errors = exc.errors()
    error_msg = "; ".join([f"{e.get('loc', ['field'])[-1]}: {e.get('msg', 'invalid')}" for e in errors])
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            success=False,
            error="Unprocessable Request Entity",
            detail=error_msg
        ).model_dump()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle general HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error="Request Failed",
            detail=str(exc.detail)
        ).model_dump()
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Fallback handler for uncaught server errors."""
    logger.exception(f"Unhandled internal error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            success=False,
            error="Internal Server Error",
            detail="An unexpected error occurred while processing the website analysis."
        ).model_dump()
    )


# --------------------------------------------------------------------------
# API Endpoints
# --------------------------------------------------------------------------

@app.get("/", tags=["General"])
async def root():
    """Root info endpoint providing API status and documentation link."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "documentation": "/docs",
        "endpoints": {
            "link_analysis": {
                "method": "POST",
                "path": "/link-analysis",
                "description": "Analyze website URL and generate 5-section AI intelligence report."
            },
            "health": {
                "method": "GET",
                "path": "/health"
            }
        }
    }


@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint for container probes and monitoring."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.LLM_PROVIDER
    }


@app.post(
    "/link-analysis",
    response_model=LinkAnalysisResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis"],
    summary="Analyze website content and generate 5-section strategic intelligence",
    responses={
        200: {"description": "Successful website analysis report", "model": LinkAnalysisResponse},
        400: {"description": "Malformed or invalid URL", "model": ErrorResponse},
        403: {"description": "Access forbidden by SSRF defense", "model": ErrorResponse},
        404: {"description": "Target website was not found", "model": ErrorResponse},
        415: {"description": "Unsupported content type (non-HTML)", "model": ErrorResponse},
        502: {"description": "Target website host unreachable", "model": ErrorResponse},
        504: {"description": "Target website gateway timed out", "model": ErrorResponse},
    }
)
async def link_analysis(payload: LinkAnalysisRequest):
    """Analyze a given website URL using an LLM to generate structured business,

    competitor, SEO, search query, and audience intelligence across 5 sections.
    """
    logger.info(f"Received link analysis request for URL: {payload.url}")

    service: AnalysisService = getattr(app.state, "analysis_service", None)
    if not service:
        service = AnalysisService()

    result = await service.analyze_url(payload.url)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
