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

## Batasan stage one

Belum ada autentikasi, unggah materi, integrasi SIBangkom, ingestion dokumen, retrieval, provider LLM, kontrak assessment, scoring, atau output penilaian nyata.
