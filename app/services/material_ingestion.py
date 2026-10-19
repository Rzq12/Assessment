import logging
from pathlib import Path

from app.schemas.material import MaterialCache
from app.services.document_parser import parse_document

logger = logging.getLogger(__name__)


def ingest_materials(source_dir: Path, cache_dir: Path) -> list[MaterialCache]:
    results: list[MaterialCache] = []
    for source_path in sorted(path for path in source_dir.iterdir() if path.is_file()):
        try:
            results.append(parse_document(source_path, source_path.stem, cache_dir))
        except (ValueError, OSError, RuntimeError) as exc:
            logger.warning("Skipping material %s (%s)", source_path.name, type(exc).__name__)
    return results
