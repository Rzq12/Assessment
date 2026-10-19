import json
import os
from pathlib import Path

import streamlit as st

from app.core.config import get_max_journal_characters
from app.core.criteria import get_passing_score, load_criteria
from app.schemas.request import AssessmentRequest
from app.services.assessment import assess_journal
from app.services.input_validation import validate_journal
from app.services.llm_evaluator import EvaluatorNotConfigured, has_live_evaluator

st.set_page_config(page_title="Penilaian Jurnal SIBangkom", page_icon="📝", layout="centered")

st.title("Penilaian Jurnal SIBangkom")
st.write("Tulis refleksi pembelajaran Anda untuk memeriksa kesiapan penilaian jurnal.")

try:
    max_characters = get_max_journal_characters()
except ValueError as exc:
    st.error(f"Konfigurasi batas karakter tidak valid: {exc}")
    st.stop()

journal = st.text_area(
    "Jurnal atau Rangkuman Pembelajaran",
    height=280,
    max_chars=max_characters,
    placeholder="Tuliskan pengalaman, pembelajaran, dan rencana tindak lanjut Anda.",
)
st.caption(f"{len(journal):,} / {max_characters:,} karakter")

if st.button("Nilai Jurnal", type="primary", use_container_width=True):
    error = validate_journal(journal, max_characters)
    if error:
        st.error(error)
    elif not has_live_evaluator():
        st.info("Mesin penilaian belum tersedia. Jurnal Anda belum dinilai.")
    else:
        try:
            with st.spinner("Menyiapkan penilaian..."):
                cache_dir = Path(os.getenv("PROCESSED_DIR", "material_cache"))
                result = assess_journal(
                    AssessmentRequest(journal_text=journal),
                    cache_dir,
                    load_criteria(),
                    passing_score=get_passing_score(),
                )
            st.subheader("Hasil penilaian")
            st.write(result.summary)
            st.metric("Skor", f"{result.score:.2f} / 100")
            st.write(f"Status: **{result.status.value}**")
            if result.review_reason:
                st.warning(result.review_reason)
            st.json(result.model_dump(mode="json"))
            st.download_button(
                "Unduh hasil JSON",
                data=json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
                file_name=f"{result.assessment_id}.json",
                mime="application/json",
            )
        except EvaluatorNotConfigured:
            st.info("Mesin penilaian belum tersedia. Jurnal Anda belum dinilai.")
        except Exception:
            st.error("Penilaian gagal karena masalah konfigurasi atau layanan. Silakan coba lagi nanti.")
