import json
import os
from pathlib import Path

import streamlit as st

from app.core.config import get_max_journal_characters
from app.core.criteria import get_passing_score, load_criteria
from app.schemas.material import MaterialCache
from app.schemas.request import AssessmentRequest
from app.services.assessment import assess_journal
from app.services.input_validation import validate_journal
from app.services.llm_evaluator import EvaluatorNotConfigured, has_live_evaluator

st.set_page_config(page_title="Jurnal Pembelajaran SIBangkom", page_icon="📝", layout="wide")
st.markdown(
    """
    <style>
    .block-container { max-width: 980px; padding-top: 2.5rem; padding-bottom: 4rem; }
    .material-panel { border: 1px solid #d9dee8; border-radius: 10px; padding: 1.15rem 1.25rem; margin: 0 0 0.85rem; }
    .source-excerpt { background: #fff8eb; border: 1px solid #e9a23b; border-radius: 8px; padding: 1rem; margin: 0.8rem 0; }
    .source-excerpt p { margin: 0.35rem 0 0; color: #394150; font-size: 0.92rem; }
    .save-status { color: #087a37; font-weight: 600; }
    @media (max-width: 640px) { .block-container { padding: 1rem 0.75rem 2rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Jurnal Pembelajaran")
st.write("Tulis refleksi untuk setiap materi. Jawaban disimpan sementara di sesi ini.")

try:
    max_characters = get_max_journal_characters()
except ValueError as exc:
    st.error(f"Konfigurasi batas karakter tidak valid: {exc}")
    st.stop()

cache_dir = Path(os.getenv("PROCESSED_DIR", "material_cache"))
materials: list[MaterialCache] = []
if cache_dir.exists():
    for cache_path in sorted(cache_dir.glob("*.json")):
        try:
            materials.append(MaterialCache.model_validate_json(cache_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue

if not materials:
    st.info("Belum ada materi yang siap digunakan. Proses materi di folder Docs Materi terlebih dahulu.")
    st.stop()

if "material_answers" not in st.session_state:
    st.session_state.material_answers = {}

for material in materials:
    material_id = material.material_id
    answer_key = f"answer_{material_id}"
    save_key = f"save_{material_id}"
    result_key = f"result_{material_id}"
    if answer_key not in st.session_state:
        st.session_state[answer_key] = st.session_state.material_answers.get(material_id, "")
    with st.expander(material_id, expanded=False):
        excerpts = []
        for chunk in material.chunks:
            excerpt = " ".join(chunk.text.split())
            if excerpt and excerpt not in excerpts:
                excerpts.append(excerpt)
            if len(excerpts) == 3:
                break
        if excerpts:
            with st.container(border=True):
                st.markdown("**Kutipan dari materi**")
                for excerpt in excerpts:
                    st.caption(excerpt)
        else:
            st.info("Belum ada kutipan teks yang tersedia untuk materi ini.")

        answer = st.text_area(
            "Rangkuman pembelajaran",
            key=answer_key,
            height=150,
            max_chars=max_characters,
            placeholder="Tuliskan hal yang Anda pelajari dan penerapannya.",
            label_visibility="collapsed",
        )
        st.caption(f"{len(answer):,} / {max_characters:,} karakter")
        save_col, assess_col = st.columns([1, 1])
        if save_col.button("Simpan", key=save_key, use_container_width=True):
            st.session_state.material_answers[material_id] = answer
            st.session_state.pop(result_key, None)
            st.rerun()
        if material_id in st.session_state.material_answers:
            st.markdown('<span class="save-status">Tersimpan di sesi ini</span>', unsafe_allow_html=True)
        if assess_col.button("Nilai materi ini", key=f"assess_{material_id}", type="primary", use_container_width=True):
            error = validate_journal(answer, max_characters)
            if error:
                st.error(error)
            elif not st.session_state.material_answers.get(material_id) == answer:
                st.info("Simpan jawaban terlebih dahulu sebelum menilai.")
            else:
                st.session_state[f"consent_{material_id}"] = True
        if st.session_state.get(f"consent_{material_id}"):
            st.warning(
                "Jawaban dan kutipan relevan materi ini akan dikirim ke 9Router "
                "(https://9router.riezqidr.my.id/v1) untuk penilaian."
            )
            consent = st.checkbox(
                "Saya menyetujui pengiriman jawaban dan kutipan materi ini untuk penilaian.",
                key=f"consent_checkbox_{material_id}",
            )
            if st.button("Konfirmasi dan nilai", key=f"confirm_{material_id}", type="primary"):
                if not consent:
                    st.info("Penilaian tidak dimulai. Beri persetujuan untuk mengirim data.")
                elif not has_live_evaluator():
                    st.info("Mesin penilaian belum tersedia. Jawaban Anda belum dinilai.")
                else:
                    try:
                        with st.spinner(f"Menilai {material_id}..."):
                            result = assess_journal(
                                AssessmentRequest(journal_text=answer, material_id=material_id),
                                cache_dir,
                                load_criteria(),
                                passing_score=get_passing_score(),
                            )
                        st.session_state[result_key] = result.model_dump(mode="json")
                        st.session_state.pop(f"consent_{material_id}", None)
                        st.rerun()
                    except EvaluatorNotConfigured:
                        st.info("Mesin penilaian belum tersedia. Jawaban Anda belum dinilai.")
                    except Exception:
                        st.error("Penilaian gagal karena masalah konfigurasi atau layanan. Silakan coba lagi nanti.")
        result = st.session_state.get(result_key)
        if result:
            st.subheader("Hasil penilaian")
            st.write(result["summary"])
            st.write(f"Status: **{result['status']}**")
            if result.get("review_required"):
                st.warning("Hasil belum dapat ditetapkan sebagai PASS atau NOT PASS. Silakan tinjau kembali materi dan jurnal.")
                if result.get("review_reason"):
                    st.caption(f"Alasan: {result['review_reason']}")
            else:
                status = result.get("status")
                if status == "pass":
                    st.success("PASS")
                elif status == "not_pass":
                    st.error("NOT PASS")
                else:
                    st.warning("Status penilaian tidak dikenali. Silakan tinjau kembali.")
