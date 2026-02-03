from fastapi import Header, HTTPException

API_KEYS = {
    "tenantA_key": "tenantA",
    "tenantB_key": "tenantB",
}

def get_tenant_id(x_api_key: str = Header(...)):
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return API_KEYS[x_api_key]