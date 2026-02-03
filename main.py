"""
Multi-Tenant SaaS API - Main Application

A secure multi-tenant document Q&A system with strict data isolation.

MULTI-TENANT SECURITY:
1. Tenant identity comes ONLY from validated X-API-KEY header
2. Client cannot spoof tenant identity in body/query
3. All document access is filtered by tenant_id
4. No cross-tenant data leakage is possible

API Keys:
- tenantA_key → Tenant A
- tenantB_key → Tenant B
"""

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
import re
import unicodedata

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# API key to tenant mapping (server-side only)
API_KEY_TO_TENANT: Dict[str, str] = {
    "tenantA_key": "tenantA",
    "tenantB_key": "tenantB",
}

# Tenant display names
TENANT_DISPLAY_NAMES: Dict[str, str] = {
    "tenantA": "Tenant A",
    "tenantB": "Tenant B",
}

# Document storage path
DOCUMENTS_BASE_PATH: str = "tenant_files"

# Security header
API_KEY_HEADER: str = "X-API-KEY"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class Document(BaseModel):
    """Document belonging to a specific tenant."""
    id: str
    tenant_id: str
    title: str
    content: str


class AskRequest(BaseModel):
    """Request model for /ask endpoint."""
    question: str = Field(..., min_length=1, max_length=1000)


class AskResponse(BaseModel):
    """Response model for /ask endpoint."""
    answer: str
    source: Optional[str] = None
    tenant: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    tenants_loaded: int
    timestamp: str


# =============================================================================
# TENANT CONTEXT
# =============================================================================

class TenantContext:
    """Immutable tenant context attached to each request."""
    def __init__(self, tenant_id: str, display_name: str):
        self._tenant_id = tenant_id
        self._display_name = display_name
    
    @property
    def tenant_id(self) -> str:
        return self._tenant_id
    
    @property
    def display_name(self) -> str:
        return self._display_name


# =============================================================================
# DOCUMENT STORAGE (TENANT-ISOLATED)
# =============================================================================

_TENANT_DOCUMENTS: Dict[str, List[Document]] = {}


def _get_tenant_folder_path(tenant_id: str) -> Path:
    """Get filesystem path for tenant's document folder."""
    return Path(DOCUMENTS_BASE_PATH) / tenant_id.lower()


def load_tenant_documents(tenant_id: str) -> List[Document]:
    """Load all documents for a specific tenant."""
    folder_path = _get_tenant_folder_path(tenant_id)
    documents: List[Document] = []
    
    if not folder_path.exists() or not folder_path.is_dir():
        logger.warning(f"Tenant folder not found: {folder_path}")
        return documents
    
    for file_path in sorted(folder_path.glob("*.txt")):
        try:
            content = file_path.read_text(encoding="utf-8").strip()
            doc = Document(
                id=f"{tenant_id}_{file_path.stem}",
                tenant_id=tenant_id,
                title=file_path.name,
                content=content
            )
            documents.append(doc)
            logger.info(f"Loaded document: {doc.title} for tenant: {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {e}")
    
    _TENANT_DOCUMENTS[tenant_id] = documents
    logger.info(f"Loaded {len(documents)} documents for tenant: {tenant_id}")
    return documents


def load_all_tenants() -> Dict[str, List[Document]]:
    """Load documents for all configured tenants."""
    tenant_ids = set(API_KEY_TO_TENANT.values())
    for tenant_id in tenant_ids:
        load_tenant_documents(tenant_id)
    logger.info(f"Loaded documents for {len(tenant_ids)} tenants")
    return _TENANT_DOCUMENTS


def get_tenant_documents(tenant_id: str) -> List[Document]:
    """Retrieve documents for a specific tenant."""
    return _TENANT_DOCUMENTS.get(tenant_id, [])


def get_loaded_tenant_count() -> int:
    """Get number of tenants with loaded documents."""
    return len(_TENANT_DOCUMENTS)


def get_tenant_document_count(tenant_id: str) -> int:
    """Get document count for a tenant."""
    return len(get_tenant_documents(tenant_id))


# =============================================================================
# SEARCH (TENANT-ISOLATED)
# =============================================================================

MIN_KEYWORD_LENGTH: int = 3
MIN_RELEVANCE_SCORE: float = 0.1

STOP_WORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "est", "en",
    "que", "qui", "dans", "pour", "sur", "avec", "ce", "cette", "ces",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
}


def _normalize_text(text: str) -> str:
    """Normalize text for accent-insensitive comparison."""
    normalized = unicodedata.normalize('NFD', text)
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents.lower()


def _extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from text."""
    text_normalized = _normalize_text(text)
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text_normalized)
    return [w for w in words if len(w) >= MIN_KEYWORD_LENGTH and w not in STOP_WORDS]


def _calculate_relevance_score(keywords: List[str], document: Document) -> float:
    """Calculate relevance score between keywords and document."""
    if not keywords:
        return 0.0
    content_normalized = _normalize_text(document.content)
    matches = sum(1 for kw in keywords if kw in content_normalized)
    return matches / len(keywords)


def search_tenant_documents(tenant_id: str, question: str) -> Tuple[Optional[str], Optional[str]]:
    """Search for answer within tenant's documents only."""
    documents = get_tenant_documents(tenant_id)
    
    if not documents:
        return "No information available for this client.", None
    
    keywords = _extract_keywords(question)
    if not keywords:
        return "No information available for this client.", None
    
    scored_docs = [(doc, _calculate_relevance_score(keywords, doc)) for doc in documents]
    scored_docs = [(doc, score) for doc, score in scored_docs if score > 0]
    
    if not scored_docs:
        return "No information available for this client.", None
    
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    best_doc, best_score = scored_docs[0]
    
    if best_score < MIN_RELEVANCE_SCORE:
        return "No information available for this client.", None
    
    # Extract relevant sentences
    sentences = re.split(r'[.!?\n]+', best_doc.content)
    relevant = [s.strip() for s in sentences if s.strip() and 
                any(kw in _normalize_text(s) for kw in keywords)]
    
    if relevant:
        answer = ". ".join(relevant[:3]) + "."
    else:
        answer = ". ".join([s.strip() for s in sentences if s.strip()][:2]) + "."
    
    return answer, best_doc.title


def list_tenant_documents(tenant_id: str) -> List[str]:
    """List document titles for a tenant."""
    return [doc.title for doc in get_tenant_documents(tenant_id)]


# =============================================================================
# MIDDLEWARE
# =============================================================================

class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware for tenant resolution from X-API-KEY header."""
    
    EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc", "/health"}
    
    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        api_key = request.headers.get(API_KEY_HEADER.lower())
        
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": f"Missing {API_KEY_HEADER} header", "error": "unauthorized"}
            )
        
        tenant_id = API_KEY_TO_TENANT.get(api_key)
        
        if not tenant_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key", "error": "unauthorized"}
            )
        
        display_name = TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id)
        request.state.tenant = TenantContext(tenant_id, display_name)
        
        return await call_next(request)


def get_current_tenant(request: Request) -> TenantContext:
    """Dependency to get tenant from request state."""
    tenant = getattr(request.state, 'tenant', None)
    if not tenant:
        raise HTTPException(status_code=500, detail="Tenant context not found")
    return tenant


# =============================================================================
# APPLICATION LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("STARTING MULTI-TENANT SAAS API")
    logger.info("=" * 60)
    
    tenant_docs = load_all_tenants()
    for tenant_id, docs in tenant_docs.items():
        logger.info(f"  - {tenant_id}: {len(docs)} documents loaded")
    
    logger.info("=" * 60)
    logger.info("API READY - Multi-tenant isolation enabled")
    logger.info("=" * 60)
    
    yield
    
    logger.info("Shutting down Multi-Tenant SaaS API...")


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

app = FastAPI(
    title="Multi-Tenant SaaS API",
    description="""
## Multi-Tenant Document Q&A API

Secure multi-tenant API for answering questions based on tenant-specific documents.

### API Keys
| API Key | Tenant |
|---------|--------|
| `tenantA_key` | Tenant A |
| `tenantB_key` | Tenant B |

### Usage
Include `X-API-KEY` header in all requests.
    """,
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TenantMiddleware)


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information."""
    return {
        "name": "Multi-Tenant SaaS API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        tenants_loaded=get_loaded_tenant_count(),
        timestamp=datetime.utcnow().isoformat()
    )


@app.post("/ask", response_model=AskResponse, tags=["Questions"])
async def ask_question(
    request: Request,
    body: AskRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Answer a question using tenant's documents.
    
    - Tenant identified from X-API-KEY header
    - Searches ONLY tenant's documents
    - Returns answer with source document
    """
    logger.info(f"Processing question for tenant: {tenant.tenant_id}")
    
    answer, source = search_tenant_documents(tenant.tenant_id, body.question)
    
    return AskResponse(
        answer=answer,
        source=source,
        tenant=tenant.display_name
    )


@app.get("/documents", response_model=List[str], tags=["Documents"])
async def get_documents(
    request: Request,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """List all documents for authenticated tenant."""
    return list_tenant_documents(tenant.tenant_id)


@app.get("/tenant/info", tags=["Tenant"])
async def get_tenant_info(
    request: Request,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Get tenant information."""
    return {
        "tenant_id": tenant.tenant_id,
        "display_name": tenant.display_name,
        "document_count": get_tenant_document_count(tenant.tenant_id)
    }


# =============================================================================
# RUN WITH UVICORN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
