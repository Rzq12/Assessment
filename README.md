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

Jalankan pengujian dengan `python -m pytest -q`. Tahap 4 menambahkan retrieval kata sederhana, orkestrasi evaluasi, dan tampilan hasil JSON. Retrieval tanpa `material_id` hanya memilih materi dengan skor yang cukup dan membedakan kandidat terbaik; jika tidak yakin hasilnya `needs_review`. Bila `material_id` tersedia, hanya potongan dari materi itu yang dipakai. Cache materi dibaca dari `PROCESSED_DIR` (default `material_cache`).

Evaluator saat ini hanya memiliki kontrak provider-netral dan mock untuk pengujian; adapter provider nyata belum dipilih atau dikonfigurasi. Tanpa provider, model, dan API key, aplikasi menampilkan mesin penilaian belum tersedia dan tidak mengarang hasil. Variabel yang akan digunakan: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, dan `LLM_TIMEOUT_SECONDS` (default 60). Unit test berjalan tanpa jaringan/API key. Evaluasi dengan provider nyata belum diverifikasi.

## Pemrosesan materi fase 3

`ingest_materials(source_dir, cache_dir)` memproses berkas PDF dan DOCX secara berurutan menurut nama berkas. Hasil disimpan sebagai JSON dengan hash SHA-256 sumber; berkas diurai ulang bila isinya berubah. Format lain, dokumen rusak, atau dokumen tanpa teks yang dapat diekstrak akan dilewati. DOCX tidak memiliki nomor halaman yang dapat diandalkan pada tahap ini; rujukan menggunakan heading dan urutan elemen. Docling dapat memerlukan model dan dependensi tambahan berukuran besar. OCR bergantung pada konfigurasi dan bahasa yang tersedia; akurasi OCR/vision belum divalidasi terhadap materi pelatihan yang sebenarnya. Tidak ada konten yang dikirim ke provider vision eksternal.
