import json

from app.services.material_retriever import retrieve_materials


def _cache(path, material_id, text):
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "source_sha256": "a" * 64,
        "material_id": material_id,
        "document_name": f"{material_id}.pdf",
        "chunks": [{
            "material_id": material_id,
            "document_name": f"{material_id}.pdf",
            "page": 1,
            "content_type": "text",
            "text": text,
            "source_ref": "page 1",
            "needs_check": False,
        }],
    }), encoding="utf-8")


def test_retrieval_filters_by_material_and_has_stable_ids(tmp_path):
    _cache(tmp_path / "one.json", "one", "Pembelajaran keselamatan kerja dan prosedur evakuasi")
    _cache(tmp_path / "two.json", "two", "Pembelajaran pengelolaan keuangan")
    first = retrieve_materials("prosedur evakuasi", "one", tmp_path)
    second = retrieve_materials("prosedur evakuasi", "one", tmp_path)
    assert len(first) == 1
    assert first[0]["material_id"] == "one"
    assert first[0]["chunk_id"] == second[0]["chunk_id"]


def test_retrieval_returns_empty_for_irrelevant_or_ambiguous_material(tmp_path):
    _cache(tmp_path / "one.json", "one", "Pembelajaran keselamatan kerja")
    _cache(tmp_path / "two.json", "two", "Pembelajaran keselamatan kerja")
    assert retrieve_materials("teori musik klasik", None, tmp_path) == []
    assert retrieve_materials("keselamatan kerja", None, tmp_path) == []


def test_malformed_cache_is_ignored(tmp_path):
    (tmp_path / "bad.json").write_text("{invalid", encoding="utf-8")
    _cache(tmp_path / "good.json", "good", "Prosedur evakuasi keselamatan")
    assert retrieve_materials("prosedur evakuasi", "good", tmp_path)
