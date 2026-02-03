"""
Multi-Tenant Middleware Module

CRITICAL SECURITY COMPONENT:
This middleware is responsible for tenant isolation at the request level.
It ensures that:
1. Every request is authenticated via X-API-KEY header
2. Tenant identity is resolved SERVER-SIDE only
3. Tenant context is attached to request.state for downstream use
4. Invalid/missing API keys result in 401 Unauthorized

ARCHITECTURE:
- Middleware intercepts ALL requests before they reach route handlers
- Tenant info is stored in request.state.tenant (not accessible to client)
- Route handlers access tenant via request.state, never from request body/query
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional

from .config import API_KEY_TO_TENANT, TENANT_DISPLAY_NAMES, API_KEY_HEADER


class TenantContext:
    """
    Immutable tenant context attached to each request.
    Contains all tenant-specific information needed for request processing.
    """
    def __init__(self, tenant_id: str, display_name: str):
        self._tenant_id = tenant_id
        self._display_name = display_name
    
    @property
    def tenant_id(self) -> str:
        """Internal tenant identifier (e.g., 'tenantA')"""
        return self._tenant_id
    
    @property
    def display_name(self) -> str:
        """Human-readable tenant name (e.g., 'Tenant A')"""
        return self._display_name
    
    def __repr__(self) -> str:
        return f"TenantContext(tenant_id='{self._tenant_id}', display_name='{self._display_name}')"


class TenantMiddleware(BaseHTTPMiddleware):
    """
    FastAPI Middleware for Multi-Tenant Resolution
    
    SECURITY FLOW:
    1. Extract X-API-KEY from request headers
    2. Validate API key against server-side mapping
    3. Resolve tenant identity from validated key
    4. Attach TenantContext to request.state
    5. Reject unauthorized requests with 401
    
    ISOLATION GUARANTEE:
    - Tenant identity comes ONLY from validated API key
    - Client cannot spoof tenant identity
    - All downstream code uses request.state.tenant
    """
    
    # Paths that don't require authentication
    EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc", "/health"}
    
    async def dispatch(self, request: Request, call_next):
        """
        Process each request for tenant resolution.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from downstream handler or 401 error
        """
        
        # Skip authentication for exempt paths (docs, health check, etc.)
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # =================================================================
        # STEP 1: Extract API Key from Header
        # =================================================================
        # SECURITY: API key MUST come from header, never body/query
        api_key: Optional[str] = request.headers.get(API_KEY_HEADER.lower())
        
        if not api_key:
            # Missing API key - reject request
            return JSONResponse(
                status_code=401,
                content={
                    "detail": f"Missing {API_KEY_HEADER} header",
                    "error": "unauthorized"
                }
            )
        
        # =================================================================
        # STEP 2: Validate API Key and Resolve Tenant
        # =================================================================
        # SECURITY: Tenant identity is resolved server-side only
        tenant_id: Optional[str] = API_KEY_TO_TENANT.get(api_key)
        
        if not tenant_id:
            # Invalid API key - reject request
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Invalid API key",
                    "error": "unauthorized"
                }
            )
        
        # =================================================================
        # STEP 3: Create and Attach Tenant Context
        # =================================================================
        # Tenant context is stored in request.state (server-side only)
        display_name = TENANT_DISPLAY_NAMES.get(tenant_id, tenant_id)
        tenant_context = TenantContext(
            tenant_id=tenant_id,
            display_name=display_name
        )
        
        # Attach to request state - accessible in route handlers
        request.state.tenant = tenant_context
        
        # =================================================================
        # STEP 4: Continue to Route Handler
        # =================================================================
        response = await call_next(request)
        return response


def get_current_tenant(request: Request) -> TenantContext:
    """
    Dependency function to extract tenant from request state.
    Use this in route handlers to access tenant context.
    
    Usage:
        @app.post("/ask")
        def ask(request: Request, tenant: TenantContext = Depends(get_current_tenant)):
            # tenant.tenant_id and tenant.display_name are available
            pass
    
    Args:
        request: FastAPI Request object
        
    Returns:
        TenantContext for the authenticated tenant
        
    Raises:
        HTTPException: If tenant not found in request state (middleware failure)
    """
    tenant = getattr(request.state, 'tenant', None)
    
    if not tenant:
        # This should never happen if middleware is properly configured
        raise HTTPException(
            status_code=500,
            detail="Tenant context not found - middleware configuration error"
        )
    
    return tenant
