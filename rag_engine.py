import chromadb
import logging
from fastapi.concurrency import run_in_threadpool
from rank_bm25 import BM25Okapi

logger = logging.getLogger("gateway.rag")

# Initialize persistent ChromaDB client for vector storage
chroma_client = chromadb.PersistentClient(path="./vector_store")
collection = chroma_client.get_or_create_collection(name="internal_knowledge")

bm25_index = None
bm25_docs = []

def _build_bm25():
    global bm25_index, bm25_docs
    try:
        data = collection.get()
        bm25_docs = data.get("documents", [])
        if bm25_docs:
            tokenized_corpus = [doc.lower().split() for doc in bm25_docs]
            bm25_index = BM25Okapi(tokenized_corpus)
    except Exception as e:
        logger.error(f"Failed to build BM25 index: {e}")

_build_bm25()

if collection.count() == 0:
    MOCK_DOCUMENTS = [
        "Internal policy: Remote work is permitted up to 3 days a week. Apply via HR portal. (Tag: HR)",
        "API Key Guidelines: All production keys must rotate every 30 days. Contact security for exceptions.",
        "Patient Data Access: Healthcare providers can only access patient PII if explicitly authorized in their EHR profile.",
        "Admin Override: System administrators have root access to reset any local environment if an alert fires."
    ]

    MOCK_METADATA = [
        {"role": "user", "topic": "hr"},
        {"role": "developer", "topic": "security"},
        {"role": "healthcare_provider", "topic": "privacy"},
        {"role": "admin", "topic": "ops"}
    ]

    MOCK_IDS = ["doc1", "doc2", "doc3", "doc4"]

    collection.add(
        documents=MOCK_DOCUMENTS,
        metadatas=MOCK_METADATA,
        ids=MOCK_IDS
    )
    logger.info("ChromaDB seeded with mock baseline data.")
    _build_bm25()
else:
    logger.info(f"Loaded existing ChromaDB collection with {collection.count()} items.")

async def add_document_to_kb(doc_id: str, document: str, role: str, topic: str):
    def _add():
        collection.add(
            documents=[document],
            metadatas=[{"role": role, "topic": topic}],
            ids=[doc_id]
        )
        _build_bm25()
    await run_in_threadpool(_add)

def _reciprocal_rank_fusion(chroma_results, bm25_scores, k=60):
    rrf_scores = {}
    
    # Process Chroma results
    for rank, doc in enumerate(chroma_results):
        if doc not in rrf_scores:
            rrf_scores[doc] = 0
        rrf_scores[doc] += 1.0 / (k + rank + 1)
        
    # Process BM25 results
    if bm25_scores is not None and bm25_docs:
        bm25_ranked = sorted(zip(bm25_docs, bm25_scores), key=lambda x: x[1], reverse=True)
        for rank, (doc, score) in enumerate(bm25_ranked):
            if score > 0:
                if doc not in rrf_scores:
                    rrf_scores[doc] = 0
                rrf_scores[doc] += 1.0 / (k + rank + 1)
            
    sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [doc for doc, score in sorted_docs]

def _query_hybrid(prompt: str, role: str, num_results: int):
    # Chroma Search
    chroma_res = collection.query(
        query_texts=[prompt],
        n_results=num_results*2, # Fetch more for RRF
        where={"role": role}
    )
    chroma_docs = chroma_res.get("documents", [[]])[0] if chroma_res.get("documents") else []
    
    # BM25 Search
    bm25_scores = None
    if bm25_index:
        tokenized_query = prompt.lower().split()
        bm25_scores = bm25_index.get_scores(tokenized_query)
        
    # Fuse
    fused_docs = _reciprocal_rank_fusion(chroma_docs, bm25_scores)
    
    # Strictly enforce role filtering: only return docs that passed Chroma's `where` filter
    filtered_fused = [doc for doc in fused_docs if doc in chroma_docs]
    
    return filtered_fused[:num_results]

async def retrieve_context_for_role(prompt: str, role: str, num_results: int = 1) -> str:
    """
    Queries the vector database using Hybrid Search (Semantic + Keyword)
    and Reciprocal Rank Fusion.
    """
    logger.debug(f"Querying hybrid RAG for role: {role}")
    try:
        results = await run_in_threadpool(_query_hybrid, prompt, role, num_results)
        if results:
            return "\n".join(results)
        return ""
    except Exception as e:
        logger.error(f"Error querying Hybrid RAG: {e}")
        return ""
