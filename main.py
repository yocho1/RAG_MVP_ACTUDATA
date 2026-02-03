from fastapi import FastAPI, Depends,Header, HTTPException
from .auth import get_tenant_id
from .models import QueryRequest, QueryResponse
from .rag import ingest_tenant, answer_question
from pydantic import BaseModel
from pathlib import Path


app = FastAPI()

class AskRequest(BaseModel):
    question: str

TENANT_KEYS = {
    "Tenant A": "tenantA_key",
    "Tenant B": "tenantB_key",
}

TENANT_FOLDERS = {
    "tenantA_key": "tenant_files/tenanta",
    "tenantB_key": "tenant_files/tenantb",
}

def mock_llm(context: str, question: str) -> str:
    """
    Naive sentence extraction:
    Returns the first line containing any keyword from the question.
    """
    question_keywords = [w.lower() for w in question.split() if len(w) > 2]

    for line in context.splitlines():
        line_lower = line.lower()
        if any(word in line_lower for word in question_keywords):
            return line.strip()
    return "No answer found."

@app.post("/ask")
def ask(request: AskRequest, x_api_key: str = Header(...)):
    # verify tenant key
    if x_api_key not in TENANT_KEYS.values():
        raise HTTPException(status_code=401, detail="Invalid API Key")
    # Load tenant documents automatically
    folder_path = Path(TENANT_FOLDERS[x_api_key])

    document = ""
    for file in folder_path.glob("*.txt"):
        with open(file, "r", encoding="utf-8") as f:
            document += f.read() + "\n"

    answer = mock_llm(document, request.question)
    return  {"answer": answer}

    
TENANTS = ["tenantA", "tenantB"]

@app.on_event("startup")
def startup():
    for tenant in TENANTS:
        ingest_tenant(tenant)


@app.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    tenant_id: str = Depends(get_tenant_id),
):
    answer = answer_question(tenant_id, request.question)

    return QueryResponse(answer=answer)
