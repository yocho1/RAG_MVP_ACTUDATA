import os
import hashlib
import numpy as np
from openai import OpenAI
from .vectorstore import add_embeddings, search


# ---------- ENV TOGGLES ----------

USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true"
VECTOR_DIM = 1536

client = OpenAI(api_key=os.getenv("OPENAI_KEY"))

# tenant_id -> list[str]
DOCUMENTS = {}


# ---------- EMBEDDINGS ----------

def embed(text: str):
    if USE_MOCK:
        # deterministic vector from text
        h = hashlib.sha256(text.encode()).digest()
        vec = np.frombuffer(h, dtype=np.uint8).astype("float32")
        repeats = VECTOR_DIM // len(vec) + 1
        full = np.tile(vec, repeats)[:VECTOR_DIM]
        return (full / np.linalg.norm(full)).tolist()

    # real OpenAI embedding
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


# ---------- FILE LOADING ----------

def load_tenant_files(tenant_id: str, base_path="app/tenant_files"):
    tenant_dir = os.path.join(base_path, tenant_id)
    if not os.path.isdir(tenant_dir):
        return []

    texts = []
    for filename in sorted(os.listdir(tenant_dir)):
        if filename.endswith(".txt"):
            file_path = os.path.join(tenant_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                texts.append(f.read().strip())

    return texts


# ---------- INGESTION ----------

def ingest_tenant(tenant_id: str):
    texts = load_tenant_files(tenant_id)
    if not texts:
        return

    embeddings = [embed(text) for text in texts]
    DOCUMENTS[tenant_id] = texts
    add_embeddings(tenant_id, embeddings)



# ---------- ANSWER GENERATION ----------

def generate_answer(prompt: str, context: str):
    """
        if USE_MOCK:
            # return retrieved context directly
            return context
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


# ---------- RAG QUERY ----------

def answer_question(tenant_id: str, question: str):
    query_embedding = embed(question)
    indices = search(tenant_id, query_embedding)
    docs = DOCUMENTS.get(tenant_id, [])

    context_chunks = [docs[i] for i in indices if i < len(docs)]
    if not context_chunks:
        return "I don't know."

    context = "\n\n".join(context_chunks)

    prompt = f"""
You must answer ONLY using the context below.
If the answer is not in the context, say "I don't know".

Context:
{context}

Question:
{question}
"""

    return generate_answer(prompt, context)
