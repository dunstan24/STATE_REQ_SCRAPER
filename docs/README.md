# Australian State Nomination Requirements Scraper

## 📖 Deskripsi Proyek
Proyek ini adalah sebuah sistem otomasi *web scraping* yang dirancang untuk mengumpulkan data persyaratan nominasi visa wilayah/negara bagian (State Nomination Visa Requirements) dari berbagai negara bagian di Australia (khususnya untuk *Skilled Visas* seperti subclass 190 dan 491). 

Scraper akan mengekstraksi informasi krusial (contohnya *General Requirements*, kriteria khusus jalur pelamar seperti *Offshore/Onshore*, hingga *Service Fee*), kemudian menormalisasikannya menjadi format data terstruktur yang mudah dianalisis (CSV, JSON, dan Excel/XLSX).

## 🚀 Fitur Utama
- **Multi-State Scraping Terpadu:** Sistem dirancang untuk melakukan scraping data secara otomatis dan berurutan untuk 8 wilayah di Australia: **ACT, NT, NSW, QLD, SA, TAS, VIC, dan WA**.
- **Kompilasi Data (Combined Output):** Meskipun menyimpan output untuk setiap negara bagian secara individu, alat ini secara otomatis akan menggabungkannya ke dalam satu file *master* berformat CSV, JSON, atau Excel (`requirements_all_states`).
- **Sistem Modular & Maintainable:** Menggunakan penanganan error per negara bagian, sehingga jika ada 1 situs negara bagian yang gagal di-scrape karena pembaruan UI/sistem anti-bot web pemerintah, negara bagian lainnya bisa terus berjalan.
- **Logging Ekstensif:** Proses terekam rapi di `main_scraper.log`, mempermudah pelacakan (debugging) apabila scraping gagal di bagian tertentu.
- **Handling Anti-Bot:** Dibekali konfigurasi headless browser (seperti `undetected_chromedriver` & Playwright helpers) yang meminimalkan risiko diblokir.

---

## 🛠️ Persyaratan (Prerequisites)
Pastikan sistem komputer Anda memiliki **Python 3.9+** terinstal, beserta akses internet yang stabil.

Kebutuhan library utama dapat dilihat pada file `requirements.txt`, termasuk namun tidak terbatas pada:

**Scraping & Automation Engines:**
- `selenium` & `webdriver-manager`: Untuk simulasi *browser* standar.
- `undetected-chromedriver`: Untuk membypass blokir antarmuka bot dasar.
- `playwright`: Engine headless canggih untuk scrape SPA atau tabel dinamis.
- `camoufox[geoip]`: Browser khusus untuk mem-bypass prokteksi tinggi antarmuka bot seperti Cloudflare Turnstile (Sangat diperlukan untuk WA dan ACT).

**Parser & Data Processing:**
- `beautifulsoup4` & `lxml`: Untuk penguraian data HTML mentah menjadi format element tree yang dapat dicari.
- `pandas`: Inti dari pemrosesan data, digunakan untuk normalisasi kolom dan normalisasi format baris tabel.
- `openpyxl`: Digunakan Pandas untuk export dan membaca file Excel langsung.

**HTTP Clients & Utilities:**
- `requests`: Mengambil HTML statis secara langsung tanpa memuat browser (digunakan di endpoint tanpa proteksi kuat).
- `python-dotenv`: Membaca environment variabels dari `.env`.

---

## 📥 Instalasi & Persiapan

1. **Clone Repository (Jika belum)**
   ```bash
   git clone <URL-REPOSITORY-ANDA>
   cd state_nomination_scrap
   ```

2. **Buat dan Aktifkan Virtual Environment (Direkomendasikan)**
   ```bash
   # Pengguna Windows:
   python -m venv myenv
   myenv\Scripts\activate
   
   # Pengguna macOS/Linux:
   python3 -m venv myenv
   source myenv/bin/activate
   ```

3. **Install Dependensi Library (Otomatis)**
   Project ini sudah dilengkapi sistem _Auto-Setup_. Anda **TIDAK PERLU** menginstall library satu-per-satu secara manual. Langsung saja jalankan file scraper utama:

   ```bash
   python src/scrapers/main_scraper.py
   ```
   
   Pada saat program baru pertama kali dijalankan, secara otomatis sistem akan mendeteksi library apa saja yang belum diinstall dan menjalankan perintah:
   - `pip install -r requirements.txt`
   - Mengunduh library *headless browser* Camoufox (`camoufox fetch`)
   - Mengunduh *browser engine* milik Playwright (`playwright install chromium`).

4. **Pengaturan Konfigurasi (Opsional)**
   Anda bisa melihat file `src/config.py` untuk menyesuaikan opsi seperti:
   - `HEADLESS_MODE = True` (Ganti `False` jika ingin melihat visualisasi browser saat *scraping*)
   - Timeout halaman
   - Format file tujuan *export*.

---

## ⚙️ Cara Menggunakan (User Guide)

Sistem ini didesain relatif *plug-and-play*. Untuk menjalankan proses ekstraksi secara total (semua wilayah negara bagian):

1. Buka Terminal / Command Prompt dan pastikan telah masuk di dalam root folder project (`state_nomination_scrap`).
2. Jalankan perintah eksekusi file utama:
   ```bash
   python src/scrapers/main_scraper.py
   ```
3. Scraper secara sekuensial akan menjalankan script per negara bagian:
   `ACT → NT → NSW → QLD → SA → TAS → VIC → WA`
4. Log interaktif akan terlihat di terminal CLI Anda serta tersimpan di file `main_scraper.log`. Jika sukses, proses tiap *state* akan memberi notifikasi berupa durasi eksekusi dan total baris data yang diekstrak.

### Lokasi Data Hasil Scraping (Output)
Semua output data akan diletakkan di dalam folder `src/scrapers/output_scrape/`:
```text
src/scrapers/output_scrape/
│
├── act/
├── nsw/
├── ... dll per negara bagian
│
└── combined/
    ├── requirements_all_states.csv
    ├── requirements_all_states.json
    └── requirements_all_states.xlsx   <-- Data Terintegrasi
```
File Excel yang dihasilkan akan diformat secara otomatis (*auto-fit* panjang kolom, dll) karena sudah tertanam fungsi *formatter* khusus di `general_tools_scrap.py`.

---

## 📁 Struktur Direktori

Berikut adalah beberapa berkas & folder krusial dalam project ini untuk dapat dipahami pengembang (Developer):

- **`/src/scrapers/main_scraper.py`**: Merupakan titik masuk operasi *scraping*. 
- **`/src/scrapers/<kode_state>_req_scraper.py`**: *Script logic* ekstraksi data milik setiap negara bagian (misal: `qld_req_scraper.py` atau `act_req_scraper.py`).
- **`/src/config.py`**: Mengatur target URLs (link situs pemerintah), mode scraping, serta variabel pendukung lainnya.
- **`/src/scrapers/general_tools_scrap.py`**: Kumpulan modul pendukung (helper), misal alat formatting Excel (*format_excel*) atau pencari nilai Service Fee (*extract_service_fee*).
- **`/requirements.txt`**: Daftar konfigurasi *environment* baku dari Python.
- **`N8N_QUICKSTART.md` / `n8n_integration.py`**: File terkait konektivitas/integrasi workflow data ke server N8N untuk otomatisasi internal tim Anda.

---

## ⚠️ Batasan dan Troubleshooting (Pemecahan Masalah)

1. **Perubahan Format/Struktur Situs Pemerintah:** Skrip web scraping akan sangat bergantung terhadap posisi elemen HTML pada situs pemerintah. Jika tiba-tiba satu negara bagian **GAGAL** dalam tahap *scrape*, sangat wajar ini dikarenakan UI *website* mereka baru saja berubah desainnya. Anda harus memodifikasi penyeleksi CSS (*CSS selectors*) atau rupa pengurai (*BeautifulSoup parsers*) dari masing-masing sub-skrip state yang ada di folder `src/scrapers/`.
2. **Keamanan Anti-bot & Cloudflare Turnstile:** Situs wilayah seperti ACT biasanya memiliki pertahanan bot (Cloudflare) yang kuat. Scraper saat ini menangani sebagian dengan *undetected-chromedriver* / *playwright*, tetapi bypass ekstra terkadang bisa tetap diblokir.
3. Anda dapat memeriksa rincian lebih detail terkait pesan error di `/main_scraper.log`.
