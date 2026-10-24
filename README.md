# SIBangkom Journal Assessment

Prototype untuk menilai jurnal atau rangkuman pembelajaran peserta pelatihan terhadap materi resmi (PDF/DOCX). Peserta menulis jurnal per materi di aplikasi Streamlit. Sistem mengambil potongan materi yang relevan, meminta evaluator LLM memberi skor mentah per kriteria, memverifikasi setiap bukti terhadap materi, lalu backend menghitung skor akhir dan status (`pass`, `not_pass`, atau `needs_review`).

## Status fitur

| Fitur | Status |
| --- | --- |
| Form jurnal per materi, penghitung dan batas karakter, simpan di sesi | Berfungsi |
| Kontrak JSON Pydantic, scoring tertimbang, syarat wajib per kriteria | Berfungsi |
| Verifikasi bukti (materi, potongan, halaman, kutipan) | Berfungsi |
| Retrieval kata sederhana, dibatasi `material_id` | Berfungsi |
| Tampilan hasil ke peserta: hanya PASS / NOT PASS (atau perlu ditinjau beserta alasannya), tanpa skor | Berfungsi |
| Pemrosesan PDF/DOCX dengan Docling dan cache JSON ber-hash | Berfungsi, perlu Docling terpasang |
| OCR untuk PDF scan dan gambar bertulisan | Berfungsi dengan RapidOCR/EasyOCR. Tesseract perlu dipasang terpisah. Akurasi pada materi asli belum divalidasi |
| Vision untuk gambar yang tidak terbaca | Perlu `VISION_ENABLED=true` dan provider LLM yang mendukung gambar. Mati secara default |
| Evaluasi dengan model sungguhan | Perlu `LLM_*` dan API key di `.env` |
| Bobot, ambang, dan syarat wajib resmi | Belum ada. Nilai sekarang adalah prototipe |

## Instalasi

Gunakan Python 3.11 atau yang lebih baru.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Isi `LLM_API_KEY` dan periksa nilai `LLM_*` lain di `.env`. Variabel yang sudah diset di shell tidak ditimpa oleh `.env`.

Docling membawa PyTorch dan mengunduh model saat pertama dipakai, jadi instalasinya besar dan pemrosesan di CPU bisa lambat. Docling hanya dipakai saat memproses materi. Aplikasi penilaian membaca hasil cache.

### OCR

`OCR_ENGINE=auto` membiarkan Docling memilih mesin yang tersedia. Pilihan lain: `rapidocr`, `easyocr`, `tesseract`, atau `none`. Untuk Tesseract, pasang binernya beserta data bahasa Indonesia (`ind`), pastikan `tesseract` ada di `PATH`, lalu set `OCR_ENGINE=tesseract`.

## Memproses materi

Letakkan berkas PDF/DOCX di `Docs Materi/` (atau direktori di `MATERIALS_DIR`), lalu jalankan:

```powershell
python -m app.ingest
```

Opsi: `--source DIR`, `--cache DIR`, dan `--force` (proses ulang walaupun berkas tidak berubah, misalnya setelah mengganti pengaturan OCR atau vision). `material_id` diambil dari nama berkas tanpa ekstensi. Hasil disimpan sebagai JSON di `PROCESSED_DIR` (default `material_cache`) beserta hash SHA-256 sumber, dan berkas hanya diproses ulang bila isinya berubah.

Perilaku parser:

- Nomor halaman PDF diambil dari Docling. DOCX tidak punya nomor halaman, jadi `page` kosong dan `source_ref` memakai heading terdekat.
- Gambar tanpa teks terbaca dan tabel yang strukturnya gagal dikenali disimpan sebagai penanda dengan `needs_check=true`. Isinya tidak ditebak.
- Bila `VISION_ENABLED=true`, gambar seperti itu dikirim ke provider LLM. Deskripsinya disimpan dengan `content_type="vision"` dan tetap `needs_check=true`. Jawaban model `TIDAK_TERBACA` atau kegagalan provider kembali menjadi penanda.
- Berkas dengan format lain, rusak, atau tanpa teks yang dapat diekstrak dilewati dan dicatat di log tanpa isinya.

## Menjalankan aplikasi

```powershell
streamlit run app.py
```

Alur per materi: tulis jurnal → **Simpan** → **Nilai materi ini** → baca pemberitahuan pengiriman data → centang persetujuan → **Konfirmasi dan nilai**. Pemberitahuan menyebut alamat `LLM_BASE_URL` yang sedang dikonfigurasi. Tanpa persetujuan, layanan penilaian tidak dipanggil. Bila evaluator belum dikonfigurasi, aplikasi menyatakan mesin penilaian belum tersedia dan tidak mengarang hasil.

## Konfigurasi

| Variabel | Fungsi | Default |
| --- | --- | --- |
| `LLM_PROVIDER` | Adapter provider. Saat ini `openai-compatible` | Kosong (mesin belum tersedia) |
| `LLM_BASE_URL` | Base URL API OpenAI-compatible | Kosong |
| `LLM_MODEL` | Nama model evaluator | Kosong |
| `LLM_API_KEY` | Kunci API | Kosong |
| `LLM_TIMEOUT_SECONDS` | Batas waktu panggilan | `60` |
| `LLM_TEMPERATURE` | Suhu sampling, 0 sampai 2 | `0` |
| `LLM_VISION_MODEL` | Model untuk vision | Sama dengan `LLM_MODEL` |
| `PASSING_SCORE` | Ambang kelulusan, 0 sampai 100 | `75` |
| `MAX_JOURNAL_CHARACTERS` | Batas karakter jurnal (`MAX_JOURNAL_CHARS` juga diterima) | `20000` |
| `CRITERIA_FILE` | File JSON kriteria | `app/core/criteria.json` |
| `MATERIALS_DIR` | Direktori materi sumber | `Docs Materi` |
| `PROCESSED_DIR` | Direktori cache materi | `material_cache` |
| `OCR_ENGINE` | `auto`, `rapidocr`, `easyocr`, `tesseract`, `none` | `auto` |
| `OCR_LANG` | Kode bahasa OCR, dipisah koma | `id,en` (`ind,eng` untuk Tesseract) |
| `VISION_ENABLED` | Kirim gambar tak terbaca ke model vision | `false` |

File kriteria berisi daftar kriteria dengan `criterion_id`, `name`, `weight` (total harus 100), dan `minimum_score` opsional sebagai syarat wajib:

```json
[
  {"criterion_id": "accuracy", "name": "Ketepatan konsep", "weight": 40, "minimum_score": 60},
  {"criterion_id": "completeness", "name": "Kelengkapan", "weight": 30},
  {"criterion_id": "understanding", "name": "Pemahaman", "weight": 20},
  {"criterion_id": "relevance", "name": "Relevansi jurnal", "weight": 10}
]
```

Bobot 40/30/20/10 dan ambang 75 adalah nilai prototipe, bukan kebijakan resmi.

## Penilaian dan status

1. Retrieval memilih potongan materi. Bila `material_id` diberikan, hanya potongan dari materi itu yang dipakai. Tanpa `material_id`, kandidat terbaik harus cukup meyakinkan dan cukup berbeda dari kandidat kedua.
2. Evaluator hanya memberi skor mentah 0 sampai 100, alasan, bukti, dan penanda kecukupan bukti per kriteria. Jurnal dikirim sebagai data di pesan pengguna, dan prompt sistem melarang model mengikuti instruksi di dalamnya.
3. Backend membuang bukti yang materi, potongan, halaman, atau kutipannya tidak cocok dengan potongan yang diambil.
4. Skor akhir = Σ skor × bobot / 100, dibulatkan dua desimal. `pass` bila skor ≥ `PASSING_SCORE` dan semua `minimum_score` terpenuhi. Selain itu `not_pass`.

| Kondisi | Hasil | `review_reason` |
| --- | --- | --- |
| Jurnal kosong atau melebihi batas | Ditolak dengan pesan validasi | - |
| Provider belum dikonfigurasi | Pesan "mesin penilaian belum tersedia" | - |
| Timeout atau kegagalan provider | Pesan error umum, tanpa hasil | - |
| Materi tidak ditemukan atau tidak relevan | `needs_review` | `material_not_found` |
| JSON model tidak valid atau skor di luar rentang | `needs_review` | `invalid_model_output` |
| Tidak ada bukti terverifikasi, atau kriteria bertanda bukti tidak cukup | `needs_review` | `insufficient_evidence` |

Log hanya mencatat ID penilaian, status, durasi, dan jenis error. Isi jurnal tidak dicatat.

## Kontrak JSON

Contoh di bawah hanya menunjukkan bentuk skema, bukan hasil penilaian nyata.

```json
{
  "schema_version": "1.0",
  "assessment_id": "ASM-1A2B3C4D5E6F",
  "status": "pass",
  "score": 85.0,
  "passing_score": 75.0,
  "summary": "Jurnal telah mencakup sebagian besar konsep utama.",
  "criteria": [
    {
      "criterion_id": "accuracy",
      "name": "Ketepatan konsep",
      "weight": 40,
      "score": 90.0,
      "weighted_score": 36.0,
      "feedback": "Konsep utama dijelaskan dengan benar."
    }
  ],
  "evidence": [
    {
      "material_id": "Manajemen pppk",
      "chunk_id": "Manajemen pppk:Manajemen pppk.pdf:12",
      "page": 3,
      "reference_text": "Teks materi yang dikutip apa adanya.",
      "explanation": "Hubungan antara jurnal dan materi."
    }
  ],
  "strengths": ["Konsep utama dijelaskan dengan tepat."],
  "improvements": ["Tambahkan pembahasan penerapan konsep."],
  "review_required": false,
  "review_reason": null
}
```

Hasil `needs_review` berisi `score` 0, `review_required: true`, dan `review_reason` terisi. Kontrak ini dipakai di backend dan untuk integrasi. Aplikasi Streamlit hanya menampilkan PASS atau NOT PASS kepada peserta, tanpa skor, rincian kriteria, maupun unduhan JSON.

## Pengujian

```powershell
python -m pytest -q
```

Unit test berjalan tanpa jaringan dan tanpa API key. Fixture test mengisolasi `.env` dan variabel lingkungan, dan provider LLM diganti objek tiruan.

Test integrasi memuat Docling dan OCR sungguhan (PDF teks, PDF scan, DOCX dengan heading dan tabel, dokumen rusak). Test ini lebih lambat dan dipisah dari run default:

```powershell
python -m pytest -m integration
```

Test integrasi dilewati otomatis bila Docling tidak dapat dimuat, dan test OCR dilewati bila tidak ada mesin OCR terpasang.

## Batasan yang diketahui

- Hasil bersifat bantuan model, bukan jaminan kebenaran.
- `content_type="ocr"` belum dibedakan. Teks hasil OCR Docling tersimpan sebagai `text`.
- Akurasi OCR dan vision pada materi pelatihan asli, kesesuaian status dengan penilai manusia, dan konsistensi antar run belum diukur.
- Evaluasi dengan provider nyata perlu diuji manual dan dicatat terpisah dari unit test.
