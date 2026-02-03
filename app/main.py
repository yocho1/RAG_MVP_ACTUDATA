"""
Multi-Tenant SaaS API - Main Application Entry Point

This is the main FastAPI application that orchestrates all components
for the multi-tenant document Q&A system.

ARCHITECTURE OVERVIEW:
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI App                              │
├─────────────────────────────────────────────────────────────────┤
│  Middleware Layer (TenantMiddleware)                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 1. Extract X-API-KEY from headers                           ││
│  │ 2. Validate API key against server-side mapping             ││
│  │ 3. Resolve tenant identity                                  ││
│  │ 4. Attach TenantContext to request.state                    ││
│  │ 5. Reject unauthorized requests (401)                       ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  Route Handlers (routes.py)                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ - POST /ask : Answer questions (tenant-isolated)            ││
│  │ - GET /health : Health check                                ││
│  │ - GET /documents : List tenant documents                    ││
│  │ - GET /tenant/info : Get tenant info                        ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  Data Layer                                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ data_loader.py : Load documents from tenant folders         ││
│  │ search.py : Keyword search within tenant documents          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘

MULTI-TENANT SECURITY GUARANTEES:
1. Tenant identity comes ONLY from validated X-API-KEY header
2. Client cannot spoof tenant identity in body/query
3. All document access is filtered by tenant_id
4. No cross-tenant data leakage is possible

STARTUP SEQUENCE:
1. Load documents for all tenants into memory
2. Register middleware for tenant resolution
3. Include API routes
4. Start accepting requests
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .middleware import TenantMiddleware
from .routes import router
from .data_loader import load_all_tenants

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# APPLICATION LIFESPAN (STARTUP/SHUTDOWN)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    STARTUP:
    - Load all tenant documents into memory
    - Documents are loaded from tenant_files/{tenant_id}/ directories
    
    SHUTDOWN:
    - Clean up resources (if any)
    """
    # =========== STARTUP ===========
    logger.info("=" * 60)
    logger.info("STARTING MULTI-TENANT SAAS API")
    logger.info("=" * 60)
    
    # Load documents for all tenants
    logger.info("Loading tenant documents...")
    tenant_docs = load_all_tenants()
    
    for tenant_id, docs in tenant_docs.items():
        logger.info(f"  - {tenant_id}: {len(docs)} documents loaded")
    
    logger.info("=" * 60)
    logger.info("API READY - Multi-tenant isolation enabled")
    logger.info("=" * 60)
    
    yield  # Application runs here
    
    # =========== SHUTDOWN ===========
    logger.info("Shutting down Multi-Tenant SaaS API...")


# =============================================================================
# FASTAPI APPLICATION INSTANCE
# =============================================================================

app = FastAPI(
    title="Multi-Tenant SaaS API",
    description="""
## Multi-Tenant Document Q&A API

A secure multi-tenant API for answering questions based on tenant-specific documents.

### Security Model

- **Authentication**: API key via `X-API-KEY` header
- **Tenant Isolation**: Complete data separation between tenants
- **No Cross-Tenant Access**: Tenant A cannot access Tenant B's documents

### API Keys

| API Key | Tenant |
|---------|--------|
| `tenantA_key` | Tenant A |
| `tenantB_key` | Tenant B |

### Usage

Include the `X-API-KEY` header in all requests:

```bash
curl -X POST "http://localhost:8000/ask" \\
  -H "X-API-KEY: tenantA_key" \\
  -H "Content-Type: application/json" \\
  -d '{"question": "What is the cancellation procedure?"}'
```
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CRITICAL: Tenant resolution middleware
# This middleware intercepts ALL requests and:
# 1. Validates X-API-KEY header
# 2. Resolves tenant identity server-side
# 3. Attaches TenantContext to request.state
# 4. Rejects unauthorized requests
app.add_middleware(TenantMiddleware)


# =============================================================================
# ROUTE REGISTRATION
# =============================================================================

# Include all API routes
app.include_router(router)


# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information.
    
    Does not require authentication.
    """
    return {
        "name": "Multi-Tenant SaaS API",
        "version": "1.0.0",
        "description": "Multi-tenant document Q&A system with strict data isolation",
        "docs": "/docs",
        "health": "/health"
    }


# =============================================================================
# RUN WITH UVICORN (for direct execution)
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
