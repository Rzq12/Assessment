# SIBangkom Journal Assessment

Stage one menyediakan formulir Streamlit untuk memasukkan jurnal pembelajaran dan memvalidasi batas karakter. Mesin penilaian belum dikonfigurasi, sehingga aplikasi tidak menampilkan skor atau hasil JSON.

## Menjalankan aplikasi

Gunakan Python 3.11 atau versi yang kompatibel.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Batas bawaan adalah 20.000 karakter. Ubah melalui environment variable sebelum menjalankan aplikasi:

```powershell
$env:MAX_JOURNAL_CHARACTERS = "10000"
streamlit run app.py
```

Nilai harus berupa bilangan bulat positif. Nilai yang tidak valid ditampilkan sebagai pesan konfigurasi dan tidak membuat halaman crash.

## Pengujian

```powershell
python -m pytest -q
```

## Backend fase 2

Fase 2 menyediakan kontrak Pydantic versi `1.0`, konfigurasi kriteria di `app/core/criteria.json`, dan scoring deterministik yang menghitung skor tertimbang di backend. Bobot bawaan 40/30/20/10 dan ambang `PASSING_SCORE=75` adalah nilai prototipe, bukan kebijakan resmi. Keluaran evaluator mentah tidak dapat menentukan skor akhir atau status. Bukti harus cocok dengan ID materi, ID potongan, halaman, dan kutipan sumber; jika bukti tidak valid atau tidak cukup, hasil memerlukan tinjauan.

Jalankan pengujian dengan `python -m pytest -q`. Fase ini belum menghubungkan evaluator ke UI dan tidak mencakup ingestion, retrieval, atau provider LLM.
