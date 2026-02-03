"""
Configuration module for multi-tenant SaaS application.
Contains all tenant mappings and security configurations.

MULTI-TENANT SECURITY:
- API keys are mapped server-side to tenant identities
- Tenant identity is NEVER trusted from client input
- All tenant resolution happens through validated API keys
"""

from typing import Dict

# =============================================================================
# API KEY TO TENANT MAPPING
# =============================================================================
# CRITICAL: This is the ONLY source of truth for tenant identification
# API keys must be validated server-side before any data access

API_KEY_TO_TENANT: Dict[str, str] = {
    "tenantA_key": "tenantA",
    "tenantB_key": "tenantB",
}

# =============================================================================
# TENANT METADATA
# =============================================================================
# Human-readable names for tenants (used in responses)

TENANT_DISPLAY_NAMES: Dict[str, str] = {
    "tenantA": "Tenant A",
    "tenantB": "Tenant B",
}

# =============================================================================
# DATA PATHS
# =============================================================================
# Base path for tenant document storage
# Each tenant has isolated folder: {BASE_PATH}/{tenant_id}/

DOCUMENTS_BASE_PATH: str = "tenant_files"

# =============================================================================
# SECURITY CONSTANTS
# =============================================================================

API_KEY_HEADER: str = "X-API-KEY"
