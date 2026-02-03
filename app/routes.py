"""
API Routes Module for Multi-Tenant SaaS

This module defines all API endpoints with strict tenant isolation.

MULTI-TENANT SECURITY:
- All routes access tenant context from request.state (set by middleware)
- Tenant is NEVER read from request body or query parameters
- All data operations are filtered by tenant_id
- Explicit error handling for unauthorized access

ENDPOINTS:
- POST /ask - Answer questions using tenant's documents
- GET /health - Health check endpoint
- GET /documents - List tenant's documents (debug)
"""

from fastapi import APIRouter, Request, Depends
from typing import List
from datetime import datetime
import logging

from .middleware import get_current_tenant, TenantContext
from .models import AskRequest, AskResponse, HealthResponse
from .search import search_tenant_documents, list_tenant_documents
from .data_loader import get_loaded_tenant_count, get_tenant_document_count

logger = logging.getLogger(__name__)

# Create router for all API endpoints
router = APIRouter()


# =============================================================================
# MAIN QUESTION ENDPOINT
# =============================================================================

@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a question",
    description="""
    Submit a question to be answered using the authenticated tenant's documents.
    
    **MULTI-TENANT SECURITY:**
    - Tenant is identified from X-API-KEY header (not request body)
    - Search is performed ONLY on the authenticated tenant's documents
    - No cross-tenant data access is possible
    
    **RESPONSE:**
    - answer: Answer extracted from tenant's documents
    - source: Source document filename (for transparency)
    - tenant: Display name of authenticated tenant
    
    If no relevant information is found, returns:
    "No information available for this client."
    """,
    responses={
        200: {
            "description": "Successful response with answer",
            "content": {
                "application/json": {
                    "example": {
                        "answer": "La résiliation doit être enregistrée dans le CRM.",
                        "source": "procedure_resiliation.txt",
                        "tenant": "Tenant A"
                    }
                }
            }
        },
        401: {
            "description": "Unauthorized - Invalid or missing API key"
        }
    }
)
async def ask_question(
    request: Request,
    body: AskRequest,
    tenant: TenantContext = Depends(get_current_tenant)
) -> AskResponse:
    """
    Answer a question using the authenticated tenant's documents.
    
    MULTI-TENANT ISOLATION FLOW:
    1. Tenant context is extracted from request.state (set by middleware)
    2. Search is performed ONLY on tenant's documents
    3. Response includes tenant info for transparency
    
    Args:
        request: FastAPI request object
        body: Request body containing the question
        tenant: TenantContext injected by dependency (from middleware)
        
    Returns:
        AskResponse with answer, source, and tenant name
    """
    logger.info(f"Processing question for tenant: {tenant.tenant_id}")
    logger.debug(f"Question: {body.question}")
    
    # =================================================================
    # SEARCH TENANT'S DOCUMENTS (ISOLATED)
    # =================================================================
    # CRITICAL: search_tenant_documents only searches within tenant's docs
    answer, source = search_tenant_documents(
        tenant_id=tenant.tenant_id,
        question=body.question
    )
    
    # =================================================================
    # BUILD RESPONSE
    # =================================================================
    response = AskResponse(
        answer=answer,
        source=source,
        tenant=tenant.display_name
    )
    
    logger.info(f"Returning answer for tenant: {tenant.display_name}")
    
    return response


# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check API health status and loaded tenant count."
)
async def health_check() -> HealthResponse:
    """
    Return API health status.
    
    Does not require authentication (exempt in middleware).
    
    Returns:
        HealthResponse with status and tenant count
    """
    return HealthResponse(
        status="healthy",
        tenants_loaded=get_loaded_tenant_count(),
        timestamp=datetime.utcnow().isoformat()
    )


# =============================================================================
# DEBUG ENDPOINTS (TENANT-ISOLATED)
# =============================================================================

@router.get(
    "/documents",
    response_model=List[str],
    summary="List tenant documents",
    description="""
    List all document titles for the authenticated tenant.
    
    **MULTI-TENANT SECURITY:**
    - Returns ONLY documents belonging to the authenticated tenant
    - Tenant is identified from X-API-KEY header
    """
)
async def list_documents(
    request: Request,
    tenant: TenantContext = Depends(get_current_tenant)
) -> List[str]:
    """
    List all document titles for the authenticated tenant.
    
    Useful for debugging and verifying tenant isolation.
    
    Args:
        request: FastAPI request object
        tenant: TenantContext from middleware
        
    Returns:
        List of document titles for the tenant
    """
    logger.info(f"Listing documents for tenant: {tenant.tenant_id}")
    
    # Get ONLY this tenant's document titles
    titles = list_tenant_documents(tenant.tenant_id)
    
    logger.info(f"Found {len(titles)} documents for tenant: {tenant.display_name}")
    
    return titles


@router.get(
    "/tenant/info",
    summary="Get tenant info",
    description="Get information about the authenticated tenant."
)
async def get_tenant_info(
    request: Request,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Return information about the authenticated tenant.
    
    Useful for verifying tenant resolution is working correctly.
    
    Args:
        request: FastAPI request object
        tenant: TenantContext from middleware
        
    Returns:
        Dict with tenant information
    """
    return {
        "tenant_id": tenant.tenant_id,
        "display_name": tenant.display_name,
        "document_count": get_tenant_document_count(tenant.tenant_id)
    }
