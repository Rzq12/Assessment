"""Process training materials into the JSON cache used by the assessment app.

Usage: python -m app.ingest [--source DIR] [--cache DIR] [--force]
"""
import argparse
import logging
import sys
from pathlib import Path

from app.core import config
from app.core.config import (
    EvaluatorNotConfigured,
    get_materials_dir,
    get_ocr_settings,
    get_processed_dir,
    is_vision_enabled,
)
from app.services.document_parser import build_image_describer
from app.services.material_ingestion import ingest_materials


def main(argv: list[str] | None = None) -> int:
    config.load_environment()
    parser = argparse.ArgumentParser(description="Proses materi PDF/DOCX menjadi cache JSON.")
    parser.add_argument("--source", type=Path, default=None, help="Direktori materi (default MATERIALS_DIR)")
    parser.add_argument("--cache", type=Path, default=None, help="Direktori cache (default PROCESSED_DIR)")
    parser.add_argument("--force", action="store_true", help="Proses ulang walaupun cache masih sesuai")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    source_dir = args.source or get_materials_dir()
    cache_dir = args.cache or get_processed_dir()
    if not source_dir.is_dir():
        print(f"Direktori materi tidak ditemukan: {source_dir}", file=sys.stderr)
        return 1
    try:
        get_ocr_settings()
    except ValueError as exc:
        print(f"Konfigurasi OCR tidak valid: {exc}", file=sys.stderr)
        return 1
    try:
        describe_image = build_image_describer()
    except EvaluatorNotConfigured as exc:
        print(f"VISION_ENABLED aktif tetapi provider LLM belum siap: {exc}", file=sys.stderr)
        return 1
    if is_vision_enabled():
        print("Vision aktif: gambar materi akan dikirim ke provider LLM yang dikonfigurasi.")

    source_count = sum(1 for path in source_dir.iterdir() if path.is_file())
    results = ingest_materials(source_dir, cache_dir, describe_image=describe_image, force=args.force)
    for cache in results:
        flagged = sum(chunk.needs_check for chunk in cache.chunks)
        print(f"OK  {cache.document_name}: {len(cache.chunks)} potongan, {flagged} perlu pemeriksaan")
    skipped = source_count - len(results)
    print(f"Selesai: {len(results)} materi tersimpan di {cache_dir}, {skipped} berkas dilewati.")
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
