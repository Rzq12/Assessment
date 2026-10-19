from pathlib import Path
from typing import Any

from app.core.material_cache import file_sha256, read_cache, write_cache
from app.schemas.material import MaterialCache, MaterialChunk

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


def _create_converter() -> Any:
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


def _item_text(item: Any) -> str:
    if hasattr(item, "text") and isinstance(item.text, str):
        return item.text.strip()
    if hasattr(item, "export_to_markdown"):
        try:
            text = item.export_to_markdown()
            if isinstance(text, str):
                return text.strip()
        except Exception:
            return ""
    return ""


def _item_label(item: Any) -> str:
    label = getattr(item, "label", "")
    return str(getattr(label, "value", label)).lower()


def _parse_items(document: Any, source_path: Path, material_id: str) -> list[MaterialChunk]:
    chunks: list[MaterialChunk] = []
    heading = ""
    is_pdf = source_path.suffix.lower() == ".pdf"
    for order, pair in enumerate(document.iterate_items(), start=1):
        item = pair[0] if isinstance(pair, tuple) else pair
        label = _item_label(item)
        text = _item_text(item)
        if "title" in label or "heading" in label:
            if text:
                heading = text
            continue
        if not text:
            continue
        is_table = "table" in label
        provenance = getattr(item, "prov", None) or []
        page: int | None = None
        needs_check = not bool(provenance)
        if is_pdf and provenance:
            page_no = getattr(provenance[0], "page_no", None)
            if isinstance(page_no, int) and page_no >= 0:
                page = page_no + 1
            else:
                needs_check = True
        source_ref = f"{heading} (element {order})" if not is_pdf else f"page {page}" if page else f"element {order}"
        chunks.append(MaterialChunk(
            material_id=material_id,
            document_name=source_path.name,
            page=page,
            content_type="table" if is_table else "text",
            text=text,
            source_ref=source_ref,
            needs_check=needs_check,
        ))
    return chunks


def parse_document(source_path: Path, material_id: str, cache_dir: Path) -> MaterialCache:
    extension = source_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported document extension: {extension or '(none)'}")
    cache_path = cache_dir / f"{material_id}.json"
    cached = read_cache(cache_path, source_path, material_id)
    if cached is not None:
        return cached
    result = _create_converter().convert(str(source_path))
    document = getattr(result, "document", None)
    if document is None:
        raise ValueError("Docling conversion returned no document")
    chunks = _parse_items(document, source_path, material_id)
    if not chunks:
        raise ValueError("Document contains no extractable text")
    cache = MaterialCache(
        source_sha256=file_sha256(source_path),
        material_id=material_id,
        document_name=source_path.name,
        chunks=chunks,
    )
    write_cache(cache_path, cache)
    return cache
