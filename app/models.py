"""
Pydantic Models for Multi-Tenant SaaS API

This module defines all data models used in the application:
- Request/Response models for API endpoints
- Internal data models for documents and tenants
- Validation schemas with Pydantic

All models include proper typing for IDE support and documentation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# =============================================================================
# DOCUMENT MODELS
# =============================================================================

class Document(BaseModel):
    """
    Represents a document belonging to a specific tenant.
    
    MULTI-TENANT ISOLATION:
    - Each document has a tenant_id field
    - Documents are loaded from tenant-specific directories
    - Search operations filter by tenant_id
    
    Attributes:
        id: Unique document identifier (typically filename)
        tenant_id: Owning tenant's identifier (e.g., 'tenantA')
        title: Document title/filename
        content: Full text content of the document
    """
    id: str = Field(..., description="Unique document identifier")
    tenant_id: str = Field(..., description="Tenant that owns this document")
    title: str = Field(..., description="Document title or filename")
    content: str = Field(..., description="Full document content")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "doc1",
                "tenant_id": "tenantA",
                "title": "procedure_resiliation.txt",
                "content": "La résiliation doit être enregistrée dans le CRM..."
            }
        }


class Tenant(BaseModel):
    """
    Represents a tenant in the multi-tenant system.
    
    Attributes:
        id: Unique tenant identifier (e.g., 'tenantA')
        name: Human-readable tenant name (e.g., 'Tenant A')
        documents: List of documents belonging to this tenant
    """
    id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Human-readable tenant name")
    documents: List[Document] = Field(default_factory=list, description="Tenant's documents")


# =============================================================================
# API REQUEST MODELS
# =============================================================================

class AskRequest(BaseModel):
    """
    Request model for the /ask endpoint.
    
    SECURITY NOTE:
    - Tenant identity is NOT included in this request
    - Tenant is resolved from X-API-KEY header by middleware
    - This prevents tenant spoofing attacks
    
    Attributes:
        question: The user's question to be answered
    """
    question: str = Field(
        ..., 
        min_length=1,
        max_length=1000,
        
        description="The question to answer using tenant's documents"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the procedure for cancellation?"
            }
        }


# =============================================================================
# API RESPONSE MODELS
# =============================================================================

class AskResponse(BaseModel):
    """
    Response model for the /ask endpoint.
    
    Attributes:
        answer: The generated answer from document search
        source: Source document filename (for transparency)
        tenant: Display name of the authenticated tenant
    """
    answer: str = Field(..., description="Answer generated from tenant's documents")
    source: Optional[str] = Field(None, description="Source document title")
    tenant: str = Field(..., description="Authenticated tenant display name")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "La résiliation doit être enregistrée dans le CRM.",
                "source": "procedure_resiliation.txt",
                "tenant": "Tenant A"
            }
        }


class ErrorResponse(BaseModel):
    """
    Standard error response model.
    
    Attributes:
        detail: Human-readable error message
        error: Error code for programmatic handling
    """
    detail: str = Field(..., description="Error message")
    error: str = Field(..., description="Error code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Invalid API key",
                "error": "unauthorized"
            }
        }


class HealthResponse(BaseModel):
    """
    Health check response model.
    
    Attributes:
        status: Service status ('healthy' or 'unhealthy')
        tenants_loaded: Number of tenants with loaded documents
        timestamp: Current server timestamp
    """
    status: str = Field(..., description="Service health status")
    tenants_loaded: int = Field(..., description="Number of tenants with documents")
    timestamp: str = Field(..., description="Server timestamp")
