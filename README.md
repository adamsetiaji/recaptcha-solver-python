# Python reCAPTCHA Solver API

API untuk menyelesaikan tantangan reCAPTCHA secara otomatis menggunakan Python, Flask, dan Playwright.

## Fitur

- Mendukung reCAPTCHA checkbox standar dan tantangan gambar (image challenge)
- Menggunakan ekstensi browser untuk meningkatkan kemampuan solver
- Antrian tugas dengan dukungan pemrosesan paralel
- Pembuatan otomatis ekstensi browser yang dibutuhkan
- Mendukung solusi gambar untuk berbagai jenis objek (bus, mobil, dll.)
- API endpoints sesuai dengan standar industri

## Endpoint API

### 1. Membuat Tugas reCAPTCHA (URL Default)

```
POST /createTask
```

Payload:
```json
{
  "clientKey": "123456789"
}
```

Response:
```json
{
  "success": 1,
  "taskId": "uuid-task-id"
}
```

### 2. Membuat Tugas reCAPTCHA (URL Kustom)

```
POST /createTaskUrl
```

Payload:
```json
{
  "clientKey": "123456789",
  "url": "https://www.example.com/recaptcha-page",
  "sitekey": "YOUR_RECAPTCHA_SITE_KEY"
}
```

Response:
```json
{
  "success": 1,
  "taskId": "uuid-task-id"
}
```

### 3. Mendapatkan Hasil Tugas

```
POST /getTaskResult
```

Payload:
```json
{
  "clientKey": "123456789",
  "taskId": "uuid-task-id"
}
```

Response (sedang diproses):
```json
{
  "success": 1,
  "message": "processing"
}
```

Response (selesai):
```json
{
  "success": 1,
  "message": "ready",
  "gRecaptchaResponse": "03AEkXODA3dGwMny5..."
}
```

Response (gagal):
```json
{
  "success": 0,
  "message": "failed",
  "error": "Error message here"
}
```

### 4. Memeriksa Status Server

```
GET /health
```

Response:
```json
{
  "status": "ok",
  "taskCount": 5,
  "queueLength": 2
}
```

## Persyaratan Sistem

- Python 3.7+
- Playwright untuk Python
- Browser Chromium
- Sistem operasi: Windows, Linux, atau macOS

## Instalasi

### Windows

1. **Siapkan Lingkungan**:
   ```
   mkdir recaptcha-solver-api
   cd recaptcha-solver-api
   mkdir extensions
   mkdir extensions\rektCaptcha
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **Instal Dependensi**:
   ```
   pip install flask python-dotenv playwright
   python -m playwright install chromium
   ```

3. **Buat .env File**:
   Buat file `.env` dengan konten sebagai berikut:

   ```
   PORT=3000
   FLASK_ENV=development
   VALID_API_KEYS=123456789,abcdefghi
   DEFAULT_RECAPTCHA_URL=https://www.google.com/recaptcha/api2/demo
   DEFAULT_RECAPTCHA_SITEKEY=6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-
   DEFAULT_HEADLESS=false
   DEFAULT_INCOGNITO=true
   MAX_PARALLEL_TASKS=5
   RETRY_COUNT=3
   RETRY_DELAY=5000
   PAGE_LOAD_TIMEOUT=30000
   ```

4. **Jalankan Aplikasi**:
   ```
   python app.py
   ```

### Linux

1. **Siapkan Lingkungan**:
   ```
   mkdir -p recaptcha-solver-api/extensions/rektCaptcha
   cd recaptcha-solver-api
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Instal Dependensi**:
   ```
   pip install flask python-dotenv playwright
   python -m playwright install chromium
   ```

3. **Instal Dependensi Sistem untuk Playwright** (diperlukan di beberapa distro Linux):
   ```
   sudo apt-get install libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 libatspi2.0-0t64 xvfb x11vnc fluxbox python3-pip python3.12-venv -y

sudo ufw allow 3000/tcp
sudo ufw allow 5900/tcp
sudo ufw status
sudo ufw reload

python3 -m venv venv
source venv/bin/activate

pip install flask python-dotenv psutil playwright

python -m playwright install chromium
****
   
   ```

4. **Buat .env File**:
   ```
   nano .env
   ```
   Salin konfigurasi yang sama seperti di bagian Windows.

5. **Jalankan Aplikasi**:
   ```
   python app.py
   ```

## Menjalankan sebagai Layanan (Linux)

1. **Buat File Layanan Systemd**:
   ```
   sudo nano /etc/systemd/system/recaptcha-solver.service
   ```

2. **Tambahkan Konfigurasi**:
   ```
   [Unit]
   Description=reCAPTCHA Solver API
   After=network.target

   [Service]
   User=<username>
   WorkingDirectory=/path/to/recaptcha-solver-api
   ExecStart=/path/to/recaptcha-solver-api/venv/bin/python app.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. **Aktifkan dan Jalankan Layanan**:
   ```
   sudo systemctl daemon-reload
   sudo systemctl enable recaptcha-solver.service
   sudo systemctl start recaptcha-solver.service
   ```

## Contoh Penggunaan

```python
import requests
import time

# URL API
API_URL = "http://localhost:3000"
API_KEY = "123456789"

# Buat tugas baru
response = requests.post(f"{API_URL}/createTask", json={"clientKey": API_KEY})
data = response.json()
task_id = data.get("taskId")

# Tunggu dan dapatkan hasil
while True:
    result = requests.post(f"{API_URL}/getTaskResult", 
                          json={"clientKey": API_KEY, "taskId": task_id})
    data = result.json()
    
    if data.get("message") == "ready":
        print(f"Token reCAPTCHA: {data.get('gRecaptchaResponse')}")
        break
    elif data.get("success") == 0:
        print(f"Error: {data.get('error')}")
        break
        
    print("Masih diproses...")
    time.sleep(5)
```

## Troubleshooting

### Ekstensi Tidak Terload

Jika ekstensi tidak terload dengan benar:

1. Pastikan direktori `extensions/rektCaptcha` ada dan dapat diakses
2. Periksa file log untuk pesan error
3. Coba jalankan browser dalam mode non-headless dengan mengatur `DEFAULT_HEADLESS=false` di `.env`

### Tantangan Gambar Tidak Terselesaikan

Jika tantangan gambar tidak terselesaikan dengan benar:

1. Perbarui fungsi `_solve_image_challenge` untuk menyesuaikan dengan jenis tantangan gambar
2. Tambahkan jenis objek target tambahan ke dalam daftar `target_objects`
3. Sesuaikan pola pemilihan tile untuk jenis tantangan spesifik

### Error Permission Denied (Linux)

Jika mengalami masalah izin:

```
chmod -R 755 extensions/
```

## Catatan Penting

- API ini lebih efektif untuk reCAPTCHA checkpoint sederhana
- Tantangan gambar mungkin memerlukan penyesuaian tambahan untuk akurasi yang lebih tinggi
- Penggunaan API ini harus sesuai dengan Ketentuan Layanan Google

## Lisensi

[MIT License](LICENSE)
