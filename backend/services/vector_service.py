import os
import re
import math
import json
import pickle
from datetime import datetime
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever

import config

_CURRENT_EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
_CURRENT_EMBEDDING_DIMS = 768
_CURRENT_DOC_PREFIX = "search_document: "
_CURRENT_QUERY_PREFIX = "search_query: "

# In-Memory caches
_EMBEDDINGS_CACHE = None
_BM25_CACHE: Dict[str, BM25Retriever] = {}
_RERANKER_CACHE = None


def _assert_local_embeddings(embeddings_instance: Any) -> None:
    """Guards against hosted cloud embeddings being injected into the local vector pipeline."""
    cls_name = type(embeddings_instance).__name__
    if any(forbidden in cls_name for forbidden in ["Google", "GenerativeAI", "OpenAI", "Cohere", "Vertex"]):
        raise RuntimeError(
            f"Architecture Boundary Violation: Hosted embedding class '{cls_name}' "
            f"cannot be used. Document embeddings must run 100% locally with Nomic/HuggingFace."
        )


class NomicHuggingFaceEmbeddings:
    """
    Embedding wrapper that enforces Nomic asymmetric prefixes:
    - 'search_document: ' for indexed chunks
    - 'search_query: ' for queries
    """
    def __init__(
        self,
        base_embeddings: Optional[HuggingFaceEmbeddings] = None,
        doc_prefix: str = _CURRENT_DOC_PREFIX,
        query_prefix: str = _CURRENT_QUERY_PREFIX
    ):
        self._base = base_embeddings
        self.doc_prefix = doc_prefix
        self.query_prefix = query_prefix

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        prefixed_texts = [
            t if t.startswith(self.doc_prefix) else f"{self.doc_prefix}{t}"
            for t in texts
        ]
        return self._base.embed_documents(prefixed_texts)

    def embed_query(self, text: str) -> List[float]:
        prefixed = text if text.startswith(self.query_prefix) else f"{self.query_prefix}{text}"
        return self._base.embed_query(prefixed)

    def __call__(self, text: str) -> List[float]:
        return self.embed_query(text)


AsymmetricNomicEmbeddings = NomicHuggingFaceEmbeddings


class IncompatibleIndexError(Exception):
    """Raised when an index manifest is missing or does not match current embedding configuration."""
    pass


class VectorService:
    """
    Vector embedding, local FAISS storage, BM25 keyword index, and BGE reranking service.
    Follows strict 100% offline retrieval architecture with zero hosted API embeddings.
    """
    
    @staticmethod
    def get_embeddings() -> NomicHuggingFaceEmbeddings:
        """Instantiates local HuggingFace embeddings with asymmetric prefix support."""
        global _EMBEDDINGS_CACHE
        if _EMBEDDINGS_CACHE is not None:
            return _EMBEDDINGS_CACHE

        model_name = getattr(config, "EMBEDDING_MODEL", _CURRENT_EMBEDDING_MODEL)
        try:
            print(f"[VectorService] Initializing local embedding model: {model_name}...")
            base_hf = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"trust_remote_code": True},
                encode_kwargs={"normalize_embeddings": True}
            )
        except Exception as e:
            fallback = getattr(config, "FALLBACK_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            print(f"[VectorService] Warning: Failed to load '{model_name}' ({e}). Falling back to '{fallback}'...")
            base_hf = HuggingFaceEmbeddings(
                model_name=fallback,
                encode_kwargs={"normalize_embeddings": True}
            )

        _assert_local_embeddings(base_hf)
        _EMBEDDINGS_CACHE = NomicHuggingFaceEmbeddings(
            base_embeddings=base_hf,
            doc_prefix=getattr(config, "DOC_EMBED_PREFIX", _CURRENT_DOC_PREFIX),
            query_prefix=getattr(config, "QUERY_EMBED_PREFIX", _CURRENT_QUERY_PREFIX)
        )
        return _EMBEDDINGS_CACHE

    @classmethod
    def save_index_manifest(
        cls,
        collection_name: str,
        chunk_count: int,
        unit_count: Optional[int] = None,
        unit_kind: str = "page",
        filename: Optional[str] = None,
        format_ext: str = "pdf",
        embedding_dims: int = _CURRENT_EMBEDDING_DIMS,
        embedding_model: str = _CURRENT_EMBEDDING_MODEL,
        document_prefix: str = _CURRENT_DOC_PREFIX,
        query_prefix: str = _CURRENT_QUERY_PREFIX
    ) -> Dict[str, Any]:
        """Saves index_manifest.json sidecar into the collection directory."""
        collection_dir = os.path.join(config.VECTOR_STORE_DIR, collection_name)
        os.makedirs(collection_dir, exist_ok=True)
        manifest_path = os.path.join(collection_dir, "index_manifest.json")

        manifest_data = {
            "doc_id": collection_name,
            "filename": filename or f"{collection_name}.{format_ext}",
            "format": format_ext,
            "unit_count": unit_count,
            "unit_kind": unit_kind,
            "embedding_model": embedding_model,
            "embedding_dims": embedding_dims,
            "document_prefix": document_prefix,
            "query_prefix": query_prefix,
            "normalized": True,
            "chunk_size": getattr(config, "CHUNK_SIZE", 1000),
            "chunk_overlap": getattr(config, "CHUNK_OVERLAP", 200),
            "chunk_count": chunk_count,
            "bm25_indexed": True,
            "built_at": datetime.utcnow().isoformat() + "Z",
            "builder_version": "2.0.0"
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        return manifest_data

    @classmethod
    def validate_index_manifest(cls, collection_name: str) -> Dict[str, Any]:
        """Validates index_manifest.json for a collection against expected embedding configuration."""
        collection_dir = os.path.join(config.VECTOR_STORE_DIR, collection_name)
        manifest_path = os.path.join(collection_dir, "index_manifest.json")

        if not os.path.exists(manifest_path):
            raise IncompatibleIndexError(f"Missing index_manifest.json in collection '{collection_name}'")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            raise IncompatibleIndexError(f"Corrupt index_manifest.json: {e}")

        expected_model = getattr(config, "EMBEDDING_MODEL", _CURRENT_EMBEDDING_MODEL)
        expected_dims = _CURRENT_EMBEDDING_DIMS
        expected_doc_prefix = getattr(config, "DOC_EMBED_PREFIX", _CURRENT_DOC_PREFIX)
        expected_query_prefix = getattr(config, "QUERY_EMBED_PREFIX", _CURRENT_QUERY_PREFIX)

        if manifest.get("embedding_model") != expected_model:
            raise IncompatibleIndexError(
                f"Embedding model mismatch: index was built with '{manifest.get('embedding_model')}', "
                f"expected '{expected_model}'"
            )

        if manifest.get("embedding_dims") != expected_dims:
            raise IncompatibleIndexError(
                f"Embedding dimension mismatch: index has dims '{manifest.get('embedding_dims')}', "
                f"expected '{expected_dims}'"
            )

        if manifest.get("document_prefix") != expected_doc_prefix or manifest.get("query_prefix") != expected_query_prefix:
            raise IncompatibleIndexError(
                f"Asymmetric prefix mismatch: index has doc='{manifest.get('document_prefix')}', query='{manifest.get('query_prefix')}', "
                f"expected doc='{expected_doc_prefix}', query='{expected_query_prefix}'"
            )

        return manifest

    @classmethod
    def create_collection(
        cls,
        chunks: List[Document],
        collection_name: str,
        api_key: str = None,
        unit_count: Optional[int] = None,
        unit_kind: str = "page",
        filename: Optional[str] = None,
        format_ext: str = "pdf"
    ) -> FAISS:
        """
        Creates and persists a FAISS vector index alongside BM25 index and index_manifest.json sidecar.
        """
        embeddings = cls.get_embeddings()
        _assert_local_embeddings(embeddings)

        collection_dir = os.path.join(config.VECTOR_STORE_DIR, collection_name)
        os.makedirs(collection_dir, exist_ok=True)

        # Standardize metadata attributes
        for idx, doc in enumerate(chunks):
            if "chunk_id" not in doc.metadata:
                doc.metadata["chunk_id"] = f"c{idx}"
            if "doc_id" not in doc.metadata:
                doc.metadata["doc_id"] = collection_name
            if "page_label" not in doc.metadata and "page" in doc.metadata:
                doc.metadata["page_label"] = doc.metadata["page"] + 1

        if unit_count is None and chunks:
            pages = [c.metadata.get("page_label", c.metadata.get("page", 0) + 1) for c in chunks if c.metadata.get("page_label") or c.metadata.get("page") is not None]
            unit_count = max(pages) if pages else len(chunks)

        print(f"[VectorService] Building local FAISS index for '{collection_name}' with {len(chunks)} chunks ({unit_count} {unit_kind}s)...")
        vector_store = FAISS.from_documents(
            documents=chunks,
            embedding=embeddings
        )
        
        # Save FAISS index
        vector_store.save_local(collection_dir)

        # Save sidecar chunks for BM25 retrieval
        chunks_pkl_path = os.path.join(collection_dir, "chunks.pkl")
        try:
            with open(chunks_pkl_path, "wb") as f:
                pickle.dump(chunks, f)
        except Exception as e:
            print(f"[VectorService] Failed to persist chunks.pkl sidecar: {e}")

        # Build and cache BM25 keyword index
        try:
            bm25 = BM25Retriever.from_documents(chunks)
            bm25.k = 6
            _BM25_CACHE[collection_name] = bm25
        except Exception as e:
            print(f"[VectorService] BM25 indexing warning: {e}")

        # Save index manifest
        cls.save_index_manifest(
            collection_name,
            chunk_count=len(chunks),
            unit_count=unit_count,
            unit_kind=unit_kind,
            filename=filename,
            format_ext=format_ext
        )

        return vector_store

    @classmethod
    def get_collection(cls, collection_name: str, api_key: str = None) -> Optional[FAISS]:
        """Loads and validates a local FAISS collection from disk."""
        collection_dir = os.path.join(config.VECTOR_STORE_DIR, collection_name)
        if not os.path.exists(collection_dir):
            print(f"[VectorService] Collection '{collection_name}' not found on disk.")
            return None

        # Validate index manifest
        try:
            cls.validate_index_manifest(collection_name)
        except IncompatibleIndexError as e:
            print(f"[VectorService] Warning: {e}")

        embeddings = cls.get_embeddings()
        _assert_local_embeddings(embeddings)
        try:
            return FAISS.load_local(
                collection_dir,
                embeddings,
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            print(f"[VectorService] Failed to load FAISS index '{collection_name}': {e}")
            return None

    @classmethod
    def get_bm25_retriever(cls, collection_name: str, chunks: List[Document] = None) -> Optional[BM25Retriever]:
        """Returns the BM25 keyword retriever for a collection."""
        if collection_name in _BM25_CACHE:
            return _BM25_CACHE[collection_name]

        if chunks:
            try:
                bm25 = BM25Retriever.from_documents(chunks)
                bm25.k = 6
                _BM25_CACHE[collection_name] = bm25
                return bm25
            except Exception as e:
                print(f"[VectorService] BM25 creation error: {e}")
                return None

        # Attempt to load from chunks.pkl
        chunks_pkl_path = os.path.join(config.VECTOR_STORE_DIR, collection_name, "chunks.pkl")
        if os.path.exists(chunks_pkl_path):
            try:
                with open(chunks_pkl_path, "rb") as f:
                    stored_chunks = pickle.load(f)
                bm25 = BM25Retriever.from_documents(stored_chunks)
                bm25.k = 6
                _BM25_CACHE[collection_name] = bm25
                return bm25
            except Exception as e:
                print(f"[VectorService] Failed to restore BM25 from chunks.pkl: {e}")

        return None

    @classmethod
    def build_retriever(
        cls,
        collection_name: str,
        chunks: Optional[List[Document]] = None,
        k: int = 4,
        rerank: bool = False
    ):
        """Builds a composite retriever combining FAISS vector search and BM25 keyword search."""
        vector_store = cls.get_collection(collection_name)
        if not vector_store and chunks:
            vector_store = cls.create_collection(chunks, collection_name)

        bm25 = cls.get_bm25_retriever(collection_name, chunks=chunks)

        class CompositeRetriever:
            def __init__(self, vs, bm, top_k, do_rerank):
                self.vs = vs
                self.bm = bm
                self.k = top_k
                self.do_rerank = do_rerank

            def invoke(self, query: str) -> List[Document]:
                retrieved = []
                if self.vs:
                    try:
                        v_docs = self.vs.as_retriever(search_kwargs={"k": self.k}).invoke(query)
                        retrieved.extend(v_docs)
                    except Exception as e:
                        print(f"[CompositeRetriever] Vector invoke error: {e}")
                if self.bm:
                    try:
                        b_docs = self.bm.invoke(query) if hasattr(self.bm, "invoke") else self.bm.get_relevant_documents(query)
                        retrieved.extend(b_docs[:self.k])
                    except Exception as e:
                        print(f"[CompositeRetriever] BM25 invoke error: {e}")

                seen = set()
                unique_docs = []
                for d in retrieved:
                    key = d.page_content.strip()
                    if key not in seen:
                        seen.add(key)
                        unique_docs.append(d)

                if self.do_rerank:
                    return VectorService.rerank_documents(query, unique_docs, top_k=self.k)
                return unique_docs[:self.k]

        return CompositeRetriever(vector_store, bm25, k, rerank)

    @classmethod
    def deduplicate_chunks(cls, documents: List[Document], threshold: float = 0.85) -> List[Document]:
        """
        R4: Removes near-duplicate candidate chunks using character 4-gram Jaccard similarity
        before reranking to maximize diversity.
        """
        if not documents:
            return []

        def get_shingles(text: str, k: int = 4) -> set:
            clean = re.sub(r'\s+', ' ', text.lower()).strip()
            if len(clean) < k:
                return {clean}
            return set(clean[i:i+k] for i in range(len(clean) - k + 1))

        kept: List[Document] = []
        kept_shingles: List[set] = []

        for d in documents:
            shingles = get_shingles(d.page_content)
            is_duplicate = False
            for prev_shingles in kept_shingles:
                intersection = len(shingles.intersection(prev_shingles))
                union = len(shingles.union(prev_shingles))
                sim = intersection / union if union > 0 else 0.0
                if sim >= threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                kept.append(d)
                kept_shingles.append(shingles)

        return kept

    @classmethod
    def rerank_documents(cls, query: str, documents: List[Document], top_k: int = 6) -> List[Document]:
        """
        Reranks retrieved candidate chunks using local BGE Cross-Encoder.
        Applies:
        - R4: Pre-rerank deduplication
        - R7: Section heading match boost (*1.15)
        - R8: Boilerplate/contact block demotion on general queries (*0.6)
        - Normalized [0, 1] relevance_score metadata attachment
        """
        if not documents:
            return []

        # Deduplicate candidates first
        unique_docs = cls.deduplicate_chunks(documents, threshold=0.85)
        if not unique_docs:
            return []

        global _RERANKER_CACHE
        reranker_model = getattr(config, "RERANKER_MODEL", "BAAI/bge-reranker-base")

        if _RERANKER_CACHE is None:
            try:
                from sentence_transformers import CrossEncoder
                print(f"[VectorService] Loading local Cross-Encoder reranker: {reranker_model}...")
                _RERANKER_CACHE = CrossEncoder(reranker_model)
            except Exception as e:
                print(f"[VectorService] Cross-Encoder initialization warning: {e}. Using heuristic scoring.")
                _RERANKER_CACHE = False

        query_lower = query.lower()
        query_words = set(re.findall(r'\b\w{3,}\b', query_lower))
        is_contact_query = any(k in query_lower for k in ["contact", "email", "phone", "mobile", "address", "call", "reach"])

        scored_docs = []

        if _RERANKER_CACHE and _RERANKER_CACHE is not False:
            try:
                pairs = [[query, doc.page_content] for doc in unique_docs]
                raw_scores = _RERANKER_CACHE.predict(pairs)
                
                for doc, raw_s in zip(unique_docs, raw_scores):
                    # Sigmoid normalization for raw CrossEncoder logits
                    import math
                    norm_score = 1.0 / (1.0 + math.exp(-float(raw_s)))

                    # R7: Section Heading Boost
                    sec_heading = (doc.metadata.get("section_heading") or "").lower()
                    if sec_heading and sec_heading != "general":
                        sec_words = set(re.findall(r'\b\w{3,}\b', sec_heading))
                        if sec_words.intersection(query_words):
                            norm_score = min(1.0, norm_score * 1.15)

                    # R8: Boilerplate / Header Block Demotion on non-contact queries
                    is_header_chunk = (
                        doc.metadata.get("block_type") == "header" or
                        doc.metadata.get("chunk_id") == "c0" and ("github.com" in doc.page_content.lower() or "mobile:" in doc.page_content.lower())
                    )
                    if is_header_chunk and not is_contact_query:
                        norm_score = norm_score * 0.45

                    doc.metadata["relevance_score"] = round(norm_score, 4)
                    scored_docs.append((doc, norm_score))

                scored_docs.sort(key=lambda x: x[1], reverse=True)
                return [doc for doc, _ in scored_docs[:top_k]]
            except Exception as e:
                print(f"[VectorService] Reranking inference error: {e}")

        # Fallback: Keyword match density scoring
        for d in unique_docs:
            text_lower = d.page_content.lower()
            match_count = sum(1 for w in query_words if w in text_lower)
            norm_score = min(1.0, match_count / (len(query_words) + 1e-5))

            # R8: Boilerplate check
            is_header_chunk = d.metadata.get("chunk_id") == "c0" and ("github.com" in text_lower or "mobile:" in text_lower)
            if is_header_chunk and not is_contact_query:
                norm_score = norm_score * 0.45

            d.metadata["relevance_score"] = round(norm_score, 4)
            scored_docs.append((d, norm_score))

        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored_docs[:top_k]]

