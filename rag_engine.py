import chromadb
from chromadb.config import Settings
import logging
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger("gateway.rag")

# Initialize persistent ChromaDB client for vector storage
chroma_client = chromadb.PersistentClient(path="./vector_store")

# Get or create a collection for our internal context
collection = chroma_client.get_or_create_collection(name="internal_knowledge")

if collection.count() == 0:
    # Seed with some mock data reflecting different role alignments
    # In a real scenario, this would be populated from internal documentation
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
else:
    logger.info(f"Loaded existing ChromaDB collection with {collection.count()} items.")

def _query_collection_sync(prompt: str, role: str, num_results: int):
    return collection.query(
        query_texts=[prompt],
        n_results=num_results,
        where={"role": role}
    )

async def retrieve_context_for_role(prompt: str, role: str, num_results: int = 1) -> str:
    """
    Queries the vector database for the given prompt, filtering by the user's role asynchronously.
    """
    logger.debug(f"Querying vector DB for role: {role}")
    try:
        results = await run_in_threadpool(_query_collection_sync, prompt, role, num_results)
        
        # results["documents"] is a list of lists of strings
        if results and results.get("documents") and len(results["documents"][0]) > 0:
            retrieved = "\n".join(results["documents"][0])
            return retrieved
        return ""
    except Exception as e:
        logger.error(f"Error querying ChromaDB: {e}")
        return ""
