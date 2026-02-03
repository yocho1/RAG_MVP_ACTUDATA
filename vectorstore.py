import os
import faiss
import numpy as np
from typing import List

VECTOR_DIM = 1536  # OpenAI embeddings size

def tenant_path(tenant_id: str):
    path = f"app/data/{tenant_id}"
    os.makedirs(path, exist_ok=True)
    return path

def load_index(tenant_id: str):
    path = tenant_path(tenant_id)
    index_file = f"{path}/index.faiss"

    if os.path.exists(index_file):
        return faiss.read_index(index_file)
    return faiss.IndexFlatL2(VECTOR_DIM)

def save_index(tenant_id: str, index):
    path = tenant_path(tenant_id)
    faiss.write_index(index, f"{path}/index.faiss")

def add_embeddings(tenant_id: str, embeddings: List[List[float]]):
    index = load_index(tenant_id)
    vectors = np.array(embeddings).astype("float32")
    index.add(vectors)
    save_index(tenant_id, index)

def search(tenant_id: str, query_embedding, k: int = 4):
    index = load_index(tenant_id)
    query_vector = np.array([query_embedding]).astype("float32")
    distances, indices = index.search(query_vector, k)
    return indices[0]
