import json

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import Dict, Any

class RAGCorrectionStore:
    def __init__(self, persist_dir="rag_corrections_db"):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection("corrections")

    def _embed(self, text: str):
        return self.model.encode([text])[0].tolist()

    def add(self, doc_text: str, correction: Dict[str, Any]):
        embedding = self._embed(doc_text)
        self.collection.add(
            embeddings=[embedding],
            documents=[doc_text],
            metadatas=[{"correction": json.dumps(correction)}],  # <-- fixed
            ids=[str(abs(hash(doc_text)))],
        )

    def query(self, doc_text: str, threshold=0.85, top_k=1) -> Dict[str, Any]:
        embedding = self._embed(doc_text)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["metadatas", "distances"],
        )
        if results["metadatas"] and results["distances"][0]:
            distance = results["distances"][0][0]
            if distance < (1 - threshold):  # cosine similarity, lower is better
                correction_str = results["metadatas"][0][0]["correction"]
                return json.loads(correction_str) if correction_str else {}
        return {}

# For direct demo/testing
if __name__ == "__main__":
    store = RAGCorrectionStore()
    # 1. Two different patients, two corrections
    doc1 = "FAX: John Doe, DOB 1990-01-01, seen by Dr. Fazal. Discharge summary included."
    correction1 = {"provider_name": "Dr. Smith", "comment": "Specialist follow-up required."}
    store.add(doc1, correction1)

    doc2 = "FAX: Jane Smith, DOB 1985-05-21, seen by Dr. Johnson. Referral for imaging."
    correction2 = {"provider_name": "Dr. Taylor", "comment": "Imaging appointment needed."}
    store.add(doc2, correction2)

    # 2. Query with exact texts
    print("\nExact match for John Doe:", store.query(doc1, threshold=0.7))
    print("Exact match for Jane Smith:", store.query(doc2, threshold=0.7))

    # 3. Query with *very similar* text for John Doe (minor difference)
    similar_doc1 = "Fax for John Doe, DOB 1990-01-01, seen by Dr. Fazal. Discharge summary included."
    print("\nMinor variation (John Doe):", store.query(similar_doc1, threshold=0.7))

    # 4. Query with *subtly different* text for Jane Smith (paraphrase)
    similar_doc2 = "Referral sent: Jane Smith, 1985-05-21, visited Dr. Johnson for imaging."
    print("Paraphrased (Jane Smith):", store.query(similar_doc2, threshold=0.7))

    # 5. Query with completely unrelated doc
    unrelated_doc = "Patient: Mike Brown, 1975-02-10, new patient consult with Dr. Patel."
    print("\nUnrelated doc:", store.query(unrelated_doc, threshold=0.7))

    # 6. Query with slightly higher threshold (more strict)
    print("\nJohn Doe, strict threshold:", store.query(similar_doc1, threshold=0.9))

