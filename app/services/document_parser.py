import io
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.config import get_llm_settings, get_ocr_settings, is_vision_enabled
from app.core.material_cache import file_sha256, read_cache, write_cache
from app.schemas.material import MaterialCache, MaterialChunk
from app.services.llm_client import ProviderRequestError

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
UNREADABLE_PICTURE_TEXT = "[Gambar tanpa teks yang dapat dibaca otomatis; perlu pemeriksaan manual]"
UNREADABLE_TABLE_TEXT = "[Tabel yang strukturnya tidak dapat dikenali otomatis; perlu pemeriksaan manual]"
VISION_UNREADABLE = "TIDAK_TERBACA"
VISION_PROMPT = (
    "Gambar ini berasal dari materi pelatihan ASN. Tuliskan ulang dalam Bahasa Indonesia semua teks "
    "yang terlihat dan jelaskan isi diagram, tabel, atau infografik secara faktual dan ringkas. "
    "Jangan menebak atau menambahkan informasi yang tidak terlihat. "
    f"Jika isi gambar tidak dapat dibaca dengan yakin, jawab hanya {VISION_UNREADABLE}."
)

ImageDescriber = Callable[[bytes], str | None]


def _create_converter() -> Any:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        EasyOcrOptions,
        PdfPipelineOptions,
        RapidOcrOptions,
        TesseractCliOcrOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    ocr = get_ocr_settings()
    options = PdfPipelineOptions()
    options.do_ocr = ocr.engine != "none"
    if ocr.engine == "easyocr":
        options.ocr_options = EasyOcrOptions(lang=ocr.languages)
    elif ocr.engine == "tesseract":
        options.ocr_options = TesseractCliOcrOptions(lang=ocr.languages)
    elif ocr.engine == "rapidocr":
        options.ocr_options = RapidOcrOptions()
    if is_vision_enabled():
        # Picture crops are only needed when they will be sent to a vision model.
        options.generate_picture_images = True
        options.images_scale = 2.0
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})


def build_image_describer() -> ImageDescriber | None:
    """Vision describer built from the LLM settings, or None when VISION_ENABLED is off."""
    if not is_vision_enabled():
        return None
    from app.services.llm_evaluator import create_client

    settings = get_llm_settings()
    client = create_client(settings)

    def describe(image_png: bytes) -> str | None:
        try:
            return client.describe_image(prompt=VISION_PROMPT, image_png=image_png, timeout=settings.timeout)
        except ProviderRequestError:
            logger.warning("Vision description failed; picture marked for manual check")
            return None

    return describe


def _item_text(item: Any, document: Any = None) -> str:
    if hasattr(item, "text") and isinstance(item.text, str):
        return item.text.strip()
    if hasattr(item, "export_to_markdown"):
        try:
            text = item.export_to_markdown(document) if document is not None else item.export_to_markdown()
            if isinstance(text, str):
                return text.strip()
        except Exception:
            return ""
    return ""


def _item_label(item: Any) -> str:
    label = getattr(item, "label", "")
    return str(getattr(label, "value", label)).lower()


def _table_is_unreliable(item: Any) -> bool:
    data = getattr(item, "data", None)
    if data is None:
        return False
    return not getattr(data, "num_rows", 0) or not getattr(data, "num_cols", 0)


def _picture_png(item: Any, document: Any) -> bytes | None:
    get_image = getattr(item, "get_image", None)
    if get_image is None:
        return None
    try:
        image = get_image(document)
    except Exception:
        return None
    if image is None:
        return None
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _describe_picture(item: Any, document: Any, describe_image: ImageDescriber | None) -> str | None:
    if describe_image is None:
        return None
    image_png = _picture_png(item, document)
    if image_png is None:
        return None
    description = (describe_image(image_png) or "").strip()
    if not description or VISION_UNREADABLE in description:
        return None
    return description


def _parse_items(
    document: Any,
    source_path: Path,
    material_id: str,
    describe_image: ImageDescriber | None = None,
) -> list[MaterialChunk]:
    chunks: list[MaterialChunk] = []
    heading = ""
    is_pdf = source_path.suffix.lower() == ".pdf"
    for order, pair in enumerate(document.iterate_items(), start=1):
        item = pair[0] if isinstance(pair, tuple) else pair
        label = _item_label(item)
        is_picture = label in {"picture", "chart"}
        is_table = "table" in label
        text = "" if is_picture else _item_text(item, document)
        if "title" in label or "heading" in label:
            if text:
                heading = text
            continue
        if label == "section_header" and text:
            # Section headers stay searchable content and also locate the elements below them.
            heading = text

        content_type = "table" if is_table else "text"
        needs_check = False
        if is_picture:
            if getattr(item, "children", None):
                # Text found inside the picture is emitted as separate child items.
                continue
            description = _describe_picture(item, document, describe_image)
            if description:
                text, content_type = description, "vision"
            else:
                text = UNREADABLE_PICTURE_TEXT
            # Vision output is a model interpretation, so it is flagged like unreadable pictures.
            needs_check = True
        elif is_table and (not text or _table_is_unreliable(item)):
            text = text or UNREADABLE_TABLE_TEXT
            needs_check = True
        if not text:
            continue

        provenance = getattr(item, "prov", None) or []
        page: int | None = None
        # DOCX elements never carry page provenance, so only PDF elements need it.
        needs_check = needs_check or (is_pdf and not provenance)
        if is_pdf and provenance:
            page_no = getattr(provenance[0], "page_no", None)
            # Docling page numbers are already 1-based.
            if isinstance(page_no, int) and page_no >= 1:
                page = page_no
            else:
                needs_check = True
        source_ref = f"{heading} (element {order})" if not is_pdf else f"page {page}" if page else f"element {order}"
        chunks.append(MaterialChunk(
            material_id=material_id,
            document_name=source_path.name,
            page=page,
            content_type=content_type,
            text=text,
            source_ref=source_ref,
            needs_check=needs_check,
        ))
    return chunks


def parse_document(
    source_path: Path,
    material_id: str,
    cache_dir: Path,
    *,
    describe_image: ImageDescriber | None = None,
    force: bool = False,
) -> MaterialCache:
    extension = source_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported document extension: {extension or '(none)'}")
    cache_path = cache_dir / f"{material_id}.json"
    if not force:
        cached = read_cache(cache_path, source_path, material_id)
        if cached is not None:
            return cached
    result = _create_converter().convert(str(source_path))
    document = getattr(result, "document", None)
    if document is None:
        raise ValueError("Docling conversion returned no document")
    chunks = _parse_items(document, source_path, material_id, describe_image)
    if all(chunk.text in {UNREADABLE_PICTURE_TEXT, UNREADABLE_TABLE_TEXT} for chunk in chunks):
        raise ValueError("Document contains no extractable text")
    cache = MaterialCache(
        source_sha256=file_sha256(source_path),
        material_id=material_id,
        document_name=source_path.name,
        chunks=chunks,
    )
    write_cache(cache_path, cache)
    return cache
