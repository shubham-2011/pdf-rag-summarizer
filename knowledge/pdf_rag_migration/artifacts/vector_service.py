from typing import List, Dict, Any, Optional
import os
import shutil
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.documents import Document
import config

try:
    from langchain.retrievers import EnsembleRetriever, ContextualCompressionRetriever
    from langchain.retrievers.document_compressors import CrossEncoderReranker
except ImportError:
    try:
        from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
        from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
    except ImportError:
        from langchain.retrievers.ensemble import EnsembleRetriever
        from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
        from langchain.retrievers.document_compressors import CrossEncoderReranker

class NomicHuggingFaceEmbeddings(Embeddings):
    """
    Nomic Embeddings Wrapper that applies asymmetric prefixes:
    - 'search_document: ' for indexed documents
    - 'search_query: ' for search queries
    """
    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5", doc_prefix: str = "search_document: ", query_prefix: str = "search_query: "):
        self.doc_prefix = doc_prefix
        self.query_prefix = query_prefix
        self._base = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"trust_remote_code": True, "device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        prefixed = [f"{self.doc_prefix}{t}" if not t.startswith(self.doc_prefix) else t for t in texts]
        return self._base.embed_documents(prefixed)

    def embed_query(self, text: str) -> List[float]:
        prefixed = f"{self.query_prefix}{text}" if not text.startswith(self.query_prefix) else text
        return self._base.embed_query(prefixed)

_HF_EMBEDDINGS_CACHE = None
_RERANKER_CACHE = None
_FAISS_CACHE: Dict[str, FAISS] = {}
_BM25_CACHE: Dict[str, BM25Retriever] = {}
_IDENTITY_CARD_CACHE: Dict[str, Dict[str, Any]] = {}

class VectorService:
    """Vector embedding, FAISS storage, Hybrid BM25+Vector search, Reranking, and Identity Card service."""
    
    @staticmethod
    def get_embeddings() -> Embeddings:
        global _HF_EMBEDDINGS_CACHE
        if _HF_EMBEDDINGS_CACHE is None:
            hf_model = "nomic-ai/nomic-embed-text-v1.5"
            print(f"[VectorService] Initializing Nomic HuggingFace Embeddings ({hf_model}) singleton with asymmetric prefixes...")
            _HF_EMBEDDINGS_CACHE = NomicHuggingFaceEmbeddings(model_name=hf_model)
        return _HF_EMBEDDINGS_CACHE

    @staticmethod
    def get_reranker():
        global _RERANKER_CACHE
        if _RERANKER_CACHE is None:
            print("[VectorService] Initializing CrossEncoderReranker singleton (BAAI/bge-reranker-base)...")
            _RERANKER_CACHE = CrossEncoderReranker(
                model=HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base", model_kwargs={"device": "cpu"}),
                top_n=6,
            )
        return _RERANKER_CACHE

    @classmethod
    def save_identity_card(cls, collection_name: str, identity_card: Dict[str, Any]) -> None:
        """Saves Document Identity Card in-memory and to disk alongside FAISS index."""
        import json
        _IDENTITY_CARD_CACHE[collection_name] = identity_card
        index_dir = os.path.join(config.VECTOR_STORE_DIR, collection_name)
        os.makedirs(index_dir, exist_ok=True)
        id_path = os.path.join(index_dir, "identity_card.json")
        try:
            with open(id_path, "w", encoding="utf-8") as f:
                json.dump(identity_card, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[VectorService] Failed to persist identity card for {collection_name}: {e}")

    @classmethod
    def get_identity_card(cls, collection_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves Document Identity Card from cache or disk, with on-demand fallback reconstruction."""
        import json
        if collection_name in _IDENTITY_CARD_CACHE:
            return _IDENTITY_CARD_CACHE[collection_name]
        index_dir = os.path.join(config.VECTOR_STORE_DIR, collection_name)
        id_path = os.path.join(index_dir, "identity_card.json")
        if os.path.exists(id_path):
            try:
                with open(id_path, "r", encoding="utf-8") as f:
                    card = json.load(f)
                    _IDENTITY_CARD_CACHE[collection_name] = card
                    return card
            except Exception as e:
                print(f"[VectorService] Failed to load identity card for {collection_name}: {e}")

        # On-demand reconstruction if vector store exists
        v_store = cls.get_collection(collection_name)
        if v_store:
            try:
                from services.document_service import DocumentService
                docs = list(v_store.docstore._dict.values())
                if docs:
                    file_name = docs[0].metadata.get("source_file", f"Document_{collection_name}")
                    page_numbers = []
                    for d in docs:
                        p = d.metadata.get("page_label", d.metadata.get("page", 1))
                        try:
                            page_numbers.append(int(p))
                        except (ValueError, TypeError):
                            page_numbers.append(1)
                    pages = max(page_numbers) if page_numbers else 1
                    card = DocumentService.generate_identity_card(docs, file_name, pages)
                    cls.save_identity_card(collection_name, card)
                    return card
            except Exception as re:
                print(f"[VectorService] On-demand identity card reconstruction warning: {re}")

        return None

    @classmethod
    def create_collection(cls, chunks: List[Document], collection_name: str, api_key: str = None, identity_card: Dict[str, Any] = None) -> FAISS:
        embeddings = cls.get_embeddings()
        index_dir = os.path.join(config.VECTOR_STORE_DIR, collection_name)
        
        if os.path.exists(index_dir):
            shutil.rmtree(index_dir)
            
        vector_store = FAISS.from_documents(chunks, embeddings)
        vector_store.save_local(index_dir)
        _FAISS_CACHE[collection_name] = vector_store
        
        # Build BM25 keyword index for exact keyword search
        try:
            bm25 = BM25Retriever.from_documents(chunks)
            _BM25_CACHE[collection_name] = bm25
        except Exception as e:
            print(f"[VectorService] BM25 indexing warning: {e}")

        # Save Identity Card if provided
        if identity_card:
            cls.save_identity_card(collection_name, identity_card)
            
        return vector_store

    @classmethod
    def get_collection(cls, collection_name: str, api_key: str = None) -> Optional[FAISS]:
        if collection_name in _FAISS_CACHE:
            return _FAISS_CACHE[collection_name]
            
        embeddings = cls.get_embeddings()
        index_dir = os.path.join(config.VECTOR_STORE_DIR, collection_name)
        
        if os.path.exists(index_dir):
            try:
                vector_store = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
                _FAISS_CACHE[collection_name] = vector_store
                return vector_store
            except Exception as e:
                print(f"[VectorService] Failed to load FAISS index: {e}")
                return None
        return None

    @classmethod
    def get_bm25_retriever(cls, collection_name: str, chunks: List[Document] = None) -> Optional[BM25Retriever]:
        if collection_name in _BM25_CACHE:
            return _BM25_CACHE[collection_name]
        
        if chunks:
            try:
                bm25 = BM25Retriever.from_documents(chunks)
                _BM25_CACHE[collection_name] = bm25
                return bm25
            except Exception as e:
                print(f"[VectorService] BM25 creation error: {e}")
                
        # To reconstruct BM25 from FAISS, retrieve documents from underlying docstore
        vector_store = cls.get_collection(collection_name)
        if vector_store:
            try:
                docs = list(vector_store.docstore._dict.values())
                if docs:
                    bm25 = BM25Retriever.from_documents(docs)
                    _BM25_CACHE[collection_name] = bm25
                    return bm25
            except Exception as e:
                print(f"[VectorService] BM25 on-demand rebuild error: {e}")
                
        return None

    @classmethod
    def build_retriever(cls, collection_name: str, chunks: List[Document] = None, k: int = 15, rerank: bool = True):
        """Builds an Ensemble (FAISS + BM25) retriever with optional CrossEncoder Reranker."""
        store = cls.get_collection(collection_name)
        if not store:
            return None
            
        dense = store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": k, "fetch_k": 30, "lambda_mult": 0.5},
        )
        
        sparse = cls.get_bm25_retriever(collection_name, chunks)
        if sparse:
            sparse.k = k
            ensemble = EnsembleRetriever(
                retrievers=[sparse, dense],
                weights=[0.5, 0.5],
            )
        else:
            ensemble = dense
            
        if not rerank:
            return ensemble

        reranker = cls.get_reranker()
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=reranker,
            base_retriever=ensemble,
        )
        return compression_retriever

