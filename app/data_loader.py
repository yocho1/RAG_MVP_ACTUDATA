"""
Document Loader Module for Multi-Tenant SaaS

This module handles loading and storing documents with strict tenant isolation.

MULTI-TENANT DATA ISOLATION:
- Documents are stored in tenant-specific dictionaries
- Each tenant's documents are loaded from separate directories
- Document retrieval requires explicit tenant_id
- No cross-tenant data access is possible

DIRECTORY STRUCTURE:
tenant_files/
├── tenanta/
│   ├── doc1.txt
│   └── doc2.txt
└── tenantb/
    ├── doc1.txt
    └── doc2.txt
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
import logging

from .models import Document
from .config import DOCUMENTS_BASE_PATH, API_KEY_TO_TENANT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# TENANT-ISOLATED DOCUMENT STORAGE
# =============================================================================
# CRITICAL: Documents are stored in separate dictionaries per tenant
# This ensures no accidental cross-tenant data access

# Global storage: tenant_id -> List[Document]
_TENANT_DOCUMENTS: Dict[str, List[Document]] = {}


# =============================================================================
# DOCUMENT LOADING FUNCTIONS
# =============================================================================

def _get_tenant_folder_path(tenant_id: str) -> Path:
    """
    Get the filesystem path for a tenant's document folder.
    
    SECURITY: Path is constructed server-side from validated tenant_id
    
    Args:
        tenant_id: Validated tenant identifier
        
    Returns:
        Path to tenant's document directory
    """
    # Normalize tenant_id to lowercase for filesystem consistency
    normalized_id = tenant_id.lower()
    return Path(DOCUMENTS_BASE_PATH) / normalized_id


def load_tenant_documents(tenant_id: str) -> List[Document]:
    """
    Load all documents for a specific tenant from filesystem.
    
    MULTI-TENANT ISOLATION:
    - Loads ONLY from the specified tenant's directory
    - Each document is tagged with tenant_id
    - Documents are stored in tenant-specific list
    
    Args:
        tenant_id: Tenant identifier (e.g., 'tenantA')
        
    Returns:
        List of Document objects for the tenant
    """
    folder_path = _get_tenant_folder_path(tenant_id)
    documents: List[Document] = []
    
    if not folder_path.exists():
        logger.warning(f"Tenant folder not found: {folder_path}")
        return documents
    
    if not folder_path.is_dir():
        logger.error(f"Tenant path is not a directory: {folder_path}")
        return documents
    
    # Load all .txt files from tenant's folder
    for file_path in sorted(folder_path.glob("*.txt")):
        try:
            content = file_path.read_text(encoding="utf-8").strip()
            
            # Create document with tenant isolation tag
            doc = Document(
                id=f"{tenant_id}_{file_path.stem}",  # Unique ID with tenant prefix
                tenant_id=tenant_id,                  # CRITICAL: Tag with tenant
                title=file_path.name,
                content=content
            )
            documents.append(doc)
            logger.info(f"Loaded document: {doc.title} for tenant: {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {e}")
    
    # Store in global tenant-specific storage
    _TENANT_DOCUMENTS[tenant_id] = documents
    logger.info(f"Loaded {len(documents)} documents for tenant: {tenant_id}")
    
    return documents


def load_all_tenants() -> Dict[str, List[Document]]:
    """
    Load documents for all configured tenants at startup.
    
    Called during FastAPI startup event to pre-load all tenant data.
    
    Returns:
        Dictionary mapping tenant_id -> List[Document]
    """
    # Get all unique tenant IDs from configuration
    tenant_ids = set(API_KEY_TO_TENANT.values())
    
    for tenant_id in tenant_ids:
        load_tenant_documents(tenant_id)
    
    logger.info(f"Loaded documents for {len(tenant_ids)} tenants")
    return _TENANT_DOCUMENTS


# =============================================================================
# DOCUMENT RETRIEVAL FUNCTIONS (TENANT-ISOLATED)
# =============================================================================

def get_tenant_documents(tenant_id: str) -> List[Document]:
    """
    Retrieve all documents for a specific tenant.
    
    MULTI-TENANT ISOLATION:
    - Returns ONLY documents belonging to the specified tenant
    - If tenant not found, returns empty list (not another tenant's data)
    
    Args:
        tenant_id: Validated tenant identifier
        
    Returns:
        List of documents for the tenant (empty if none found)
    """
    return _TENANT_DOCUMENTS.get(tenant_id, [])


def get_document_by_title(tenant_id: str, title: str) -> Optional[Document]:
    """
    Get a specific document by title for a tenant.
    
    MULTI-TENANT ISOLATION:
    - Searches ONLY within the specified tenant's documents
    - Returns None if not found (not cross-tenant search)
    
    Args:
        tenant_id: Validated tenant identifier
        title: Document title to search for
        
    Returns:
        Document if found, None otherwise
    """
    documents = get_tenant_documents(tenant_id)
    
    for doc in documents:
        if doc.title.lower() == title.lower():
            return doc
    
    return None


def get_loaded_tenant_count() -> int:
    """
    Get the number of tenants with loaded documents.
    
    Returns:
        Count of tenants in storage
    """
    return len(_TENANT_DOCUMENTS)


def get_tenant_document_count(tenant_id: str) -> int:
    """
    Get the number of documents for a specific tenant.
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        Number of documents for the tenant
    """
    return len(get_tenant_documents(tenant_id))
