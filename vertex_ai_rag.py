"""Example script using Google Vertex AI Vector Search with LangChain.

This script demonstrates creating a vector store backed by Google Cloud's
Vector Search and indexing documents using the ``gemini-embedding-001``
model. It then performs a similarity search that can be used in RAG
pipelines.
"""

from __future__ import annotations

from typing import List

from google.cloud import aiplatform
from langchain_community.embeddings import VertexAIEmbeddings
from langchain_community.vectorstores import MatchingEngine
from langchain_core.documents import Document

# Update these constants with your configuration
PROJECT_ID = "your-project-id"
REGION = "us-central1"
BUCKET_NAME = "your-bucket"


def create_vector_store(display_name: str, dimensions: int) -> MatchingEngine:
    """Create a new Vertex AI Vector Search index and return a VectorStore."""
    aiplatform.init(project=PROJECT_ID, location=REGION, staging_bucket=f"gs://{BUCKET_NAME}")

    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=display_name,
        dimensions=dimensions,
        approximate_neighbors_count=150,
        distance_measure_type="DOT_PRODUCT_DISTANCE",
        index_update_method="STREAM_UPDATE",
    )

    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=f"{display_name}-endpoint",
    )
    endpoint.deploy_index(index)

    embedding = VertexAIEmbeddings(model_name="gemini-embedding-001")

    store = MatchingEngine.from_components(
        project_id=PROJECT_ID,
        region=REGION,
        gcs_bucket_name=BUCKET_NAME,
        index_id=index.resource_name,
        endpoint_id=endpoint.resource_name,
        embedding=embedding,
    )
    return store


def add_documents(store: MatchingEngine, texts: List[str], metadatas: List[dict]) -> None:
    """Add documents with metadata to the vector store."""
    docs = [Document(page_content=t, metadata=m) for t, m in zip(texts, metadatas)]
    store.add_documents(docs, is_complete_overwrite=True)


def search(store: MatchingEngine, query: str, k: int = 5) -> List[Document]:
    """Run a similarity search against the store."""
    return store.similarity_search(query, k=k)


if __name__ == "__main__":
    vector_store = create_vector_store("demo-index", dimensions=768)

    sample_texts = [
        "Example text about machine learning.",
        "Another document discussing artificial intelligence.",
    ]
    sample_metadata = [
        {"source": "doc1"},
        {"source": "doc2"},
    ]

    add_documents(vector_store, sample_texts, sample_metadata)

    results = search(vector_store, "What is artificial intelligence?", k=2)
    for doc in results:
        print(doc.metadata, doc.page_content)
