import streamlit as st

from app.core.config import get_max_journal_characters
from app.services.input_validation import validate_journal

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
    else:
        with st.spinner("Menyiapkan penilaian..."):
            st.info("Mesin penilaian belum tersedia. Jurnal Anda belum dinilai.")
