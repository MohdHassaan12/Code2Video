"""ChromaDB RAG — error->repair pairs (self-healing) + expert component snippets.
Enable with CHROMADB_ENABLED=1. init() is called once from the package __init__."""
import os
import logging

logger = logging.getLogger(__name__)
from .. import paths as _paths

_CHROMA_COLLECTION = None            # manim_error_fixes


_CHROMA_COMPONENTS_COLLECTION = None # manim_components


def _init_chroma():
    global _CHROMA_COLLECTION, _CHROMA_COMPONENTS_COLLECTION
    if os.getenv("CHROMADB_ENABLED", "").strip() != "1":
        return
    try:
        import chromadb  # noqa: PLC0415
        _chroma_client = chromadb.PersistentClient(
            path=str(_paths.sub("chroma_db"))
        )
        _CHROMA_COLLECTION = _chroma_client.get_or_create_collection(
            name="manim_error_fixes",
            metadata={"description": "Successful Manim error→repair pairs for self-healing RAG"},
        )
        logger.info("ChromaDB 'manim_error_fixes' ready (%d entries)", _CHROMA_COLLECTION.count())
        _CHROMA_COMPONENTS_COLLECTION = _chroma_client.get_or_create_collection(
            name="manim_components",
            metadata={"description": "Expert Manim component examples for codegen inspiration"},
        )
        logger.info("ChromaDB 'manim_components' ready (%d entries)", _CHROMA_COMPONENTS_COLLECTION.count())
    except Exception as _e:
        logger.warning("ChromaDB init failed — RAG disabled: %s", _e)


def _retrieve_past_fixes(error_msg: str, n_results: int = 3) -> list:
    """Return up to n_results similar past error→fix dicts from ChromaDB, or []."""
    if _CHROMA_COLLECTION is None:
        return []
    try:
        count = _CHROMA_COLLECTION.count()
        if count == 0:
            return []
        results = _CHROMA_COLLECTION.query(
            query_texts=[error_msg],
            n_results=min(n_results, count),
            include=["documents", "metadatas"],
        )
        fixes = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            fixes.append({
                "error": doc,
                "fixed_snippet": meta.get("fixed_snippet", ""),
                "error_type": meta.get("error_type", "unknown"),
            })
        return fixes
    except Exception as _e:
        logger.warning("ChromaDB retrieval failed: %s", _e)
        return []


def _store_repair_pair(error_msg: str, broken_code: str, fixed_code: str, scene_class: str = ""):
    """Persist a successful error→repair pair for future RAG retrieval."""
    if _CHROMA_COLLECTION is None:
        return
    try:
        import hashlib
        doc_id = hashlib.sha1((error_msg + broken_code).encode()).hexdigest()[:16]
        err_lower = error_msg.lower()
        if "layout_violation" in err_lower or "exceeds frame" in err_lower:
            error_type = "layout_overflow"
        elif "syntaxerror" in err_lower or "indentationerror" in err_lower:
            error_type = "syntax"
        elif "angle" in err_lower or "arc" in err_lower:
            error_type = "manim_angle"
        elif "svgmobject" in err_lower or "filenotfounderror" in err_lower:
            error_type = "svg_asset"
        elif "nameerror" in err_lower or "attributeerror" in err_lower:
            error_type = "name_attribute"
        elif "typeerror" in err_lower:
            error_type = "type"
        else:
            error_type = "unknown"
        _CHROMA_COLLECTION.upsert(
            ids=[doc_id],
            documents=[error_msg[:2000]],
            metadatas=[{
                "broken_snippet": broken_code[:3000],
                "fixed_snippet": fixed_code[:3000],
                "error_type": error_type,
                "scene_class": scene_class,
            }],
        )
        logger.info("Stored repair pair (error_type=%s id=%s)", error_type, doc_id)
    except Exception as _e:
        logger.warning("ChromaDB store failed: %s", _e)


def _retrieve_manim_components(query_text: str, n_results: int = 2) -> list:
    """Return up to n_results expert Manim component dicts from the manim_components collection."""
    if _CHROMA_COMPONENTS_COLLECTION is None or not query_text:
        return []
    try:
        count = _CHROMA_COMPONENTS_COLLECTION.count()
        if count == 0:
            return []
        results = _CHROMA_COMPONENTS_COLLECTION.query(
            query_texts=[query_text],
            n_results=min(n_results, count),
            include=["metadatas"],
        )
        components = []
        for meta in results.get("metadatas", [[]])[0]:
            if meta:
                components.append({
                    "class_name": meta.get("class_name", "Component"),
                    "summary":    meta.get("summary", ""),
                    "code":       meta.get("class_code") or meta.get("code", ""),
                })
        return components
    except Exception as _e:
        logger.warning("ChromaDB manim_components retrieval failed: %s", _e)
        return []
