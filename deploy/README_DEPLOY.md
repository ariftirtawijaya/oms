# RelayLab OMS — Deployment di VPS Multi-Project (/order/)

Target: satu VPS Ubuntu 24.04 (2 vCPU, 4 GB RAM, 80 GB SSD) yang menjalankan beberapa aplikasi sekaligus:

| URL | Aplikasi | Dikelola oleh |
|---|---|---|
| `https://relaylab.id/` | Landing page | Nginx utama (file statis) |
| `https://relaylab.id/presensi/` | Presensi PHP + MySQL/MariaDB | Nginx utama + PHP-FPM |
| `https://relaylab.id/order/` | **RelayLab OMS** | Nginx utama → Docker (127.0.0.1:8100) |
| `https://relaylab.id/order/api/` | API FastAPI OMS | Nginx utama → Docker (127.0.0.1:8101) |
| `https://relaylab.id/order/api/webhooks/fonnte` | Webhook Fonnte | idem |

```
Internet ─► Nginx utama VPS (80/443, HTTPS certbot)
              ├─ /            → /var/www/relaylab-landing
              ├─ /presensi/   → PHP-FPM ─► MySQL/MariaDB (host)
              ├─ /order/api/  → 127.0.0.1:8101 ─► [backend FastAPI] ─► [mongo] (jaringan Docker internal)
              └─ /order/      → 127.0.0.1:8100 ─► [frontend nginx statis]
```

Prinsip:
- Docker Compose OMS **tidak memakai port 80/443** dan tidak membawa Nginx/Certbot sendiri. Port OMS hanya terikat ke `127.0.0.1`, jadi tidak bisa diakses langsung dari internet.
- **Prefix `/order` hanya dibuang sekali, di Nginx utama.** `proxy_pass .../api/` dan `proxy_pass .../` (dengan garis miring di akhir) membuat backend tetap menerima `/api/...` dan frontend menerima `/static/...`. Jangan menambah prefix `/order` di FastAPI.
- MongoDB khusus OMS ada di jaringan Docker `relaylab-oms-net` tanpa port publik. MySQL/MariaDB aplikasi PHP tetap di host, tanpa konflik.
- Production memakai build React statis (bukan dev server), 1 worker Uvicorn, dan cache WiredTiger MongoDB 256 MB.

## 1. Struktur & volume persisten
```
/opt/relaylab-oms/            ← source code (git clone)
└── deploy/
    ├── docker-compose.yml
    ├── .env                    ← salinan .env.example (rahasia, jangan di-commit)
    ├── nginx/relaylab.id.conf.example
    ├── scripts/backup.sh, restore.sh
    ├── data/mongo/             ← DATABASE MongoDB (persisten)
    ├── data/uploads/resi/      ← FOTO RESI (persisten)
    ├── data/uploads/products/
    └── backups/                ← hasil backup
```
`data/` berupa bind mount di disk host. Folder ini tidak terhapus oleh `docker compose down`, rebuild image, maupun update aplikasi.

Batas memori bawaan: mongo 640 MB, backend 320 MB, frontend 64 MB, totalnya ±1 GB. Sisanya untuk PHP-FPM, MySQL, dan Nginx.

## 2. Instalasi pertama
```bash
# Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

sudo git clone <repo-anda> /opt/relaylab-oms && sudo chown -R $USER /opt/relaylab-oms
cd /opt/relaylab-oms/deploy
cp .env.example .env
nano .env
```
Variabel penting di `.env`:

| Variabel | Contoh | Keterangan |
|---|---|---|
| `OMS_PUBLIC_URL` | `https://relaylab.id/order` | URL publik OMS tanpa `/api` dan tanpa `/` di akhir. Frontend memanggil `${OMS_PUBLIC_URL}/api/...` |
| `OMS_BASE_PATH` | `/order` | Subdirektori (basename React Router + path aset JS/CSS/gambar) |
| `COOKIE_PATH` | `/order` | Cookie login hanya berlaku di /order |
| `CORS_ORIGINS` | `https://relaylab.id` | Origin frontend |
| `OMS_FRONTEND_PORT` / `OMS_BACKEND_PORT` | `8100` / `8101` | Port lokal; ganti bila bentrok dengan aplikasi lain |
| `MONGO_ROOT_PASSWORD`, `JWT_SECRET` (`openssl rand -hex 32`), `ADMIN_EMAIL`, `ADMIN_PASSWORD` | | Wajib diganti |

Jika suatu saat path diubah (misal `/oms`), ubah `OMS_PUBLIC_URL`, `OMS_BASE_PATH`, dan `COOKIE_PATH` bersamaan, sesuaikan blok Nginx, lalu build ulang frontend.

```bash
mkdir -p data/mongo data/uploads/resi data/uploads/products backups
sudo chown -R 1000:1000 data/uploads        # user kontainer backend (uid 1000)
chmod +x scripts/*.sh
docker compose up -d --build                # build pertama ±5–10 menit
docker compose ps
curl -s http://127.0.0.1:8101/api/health    # {"status":"ok"}
curl -sI http://127.0.0.1:8100/ | head -1   # HTTP/1.1 200 OK
```
Tips untuk RAM 4 GB: jika build frontend kehabisan memori, tambahkan swap 2 GB (`sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`).

## 3. Nginx utama + HTTPS
Salin **blok "RelayLab OMS"** dari `deploy/nginx/relaylab.id.conf.example` ke server block `relaylab.id` yang sudah ada. Jangan menimpa konfigurasi landing page dan presensi; contoh landing/presensi di file itu hanya ilustrasi.
```bash
sudo nano /etc/nginx/sites-available/relaylab.id     # tempel upstream + 3 location OMS
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d relaylab.id -d www.relaylab.id   # HTTPS + auto-renew (systemd timer)
```
Blok OMS berisi:
- `location = /order` → redirect ke `/order/`
- `location ^~ /order/api/` → `proxy_pass http://127.0.0.1:8101/api/;`
- `location ^~ /order/` → `proxy_pass http://127.0.0.1:8100/;`. Refresh halaman seperti `/order/admin/orders/123` dilayani oleh `try_files ... /index.html` di kontainer frontend.

Buka `https://relaylab.id/order/`, lalu login dengan `ADMIN_EMAIL` / `ADMIN_PASSWORD`. Akun Super Admin hanya dibuat sekali; segera ganti password lewat menu Ganti Password.

## 4. Restart & log
```bash
cd /opt/relaylab-oms/deploy
docker compose restart backend          # mis. setelah mengubah .env (variabel backend)
docker compose restart                  # semua layanan OMS
docker compose logs -f --tail=100 backend
docker stats --no-stream                # cek pemakaian RAM/CPU
```
Kontainer memakai `restart: unless-stopped`, sehingga otomatis hidup lagi setelah VPS reboot.

## 5. Update aplikasi (database & foto tetap aman)
```bash
cd /opt/relaylab-oms && git pull
cd deploy
./scripts/backup.sh
docker compose up -d --build            # hanya mengganti image; data/ tidak disentuh
docker image prune -f                   # bersihkan image lama
```
**Jangan pernah** menjalankan `docker compose down -v` atau menghapus folder `deploy/data/`.

## 6. Backup & restore
```bash
./scripts/backup.sh
# hasil: backups/mongo-YYYYMMDD-HHMMSS.archive.gz  (database)
#        backups/uploads-YYYYMMDD-HHMMSS.tar.gz    (foto resi)
./scripts/restore.sh backups/mongo-XXXX.archive.gz backups/uploads-XXXX.tar.gz
```
Backup otomatis setiap jam 02:00 (`crontab -e`):
```
0 2 * * * cd /opt/relaylab-oms/deploy && ./scripts/backup.sh >> backups/backup.log 2>&1
```
Backup yang lebih dari 30 hari dihapus otomatis. Salin folder `backups/` ke luar VPS secara berkala (rclone/NAS/Google Drive). Backup MySQL presensi dilakukan terpisah (mysqldump) dan tidak terganggu oleh OMS.

## 7. WhatsApp Fonnte
1. Isi `FONNTE_TOKEN`, `FONNTE_ADMIN_WA` (pisahkan koma; juga whitelist `/pengumuman`), `FONNTE_GROUP_ID`, dan `FONNTE_WEBHOOK_SECRET`.
2. Set `WHATSAPP_MODE=live`, lalu jalankan `docker compose up -d backend`.
3. URL webhook di dashboard Fonnte: `https://relaylab.id/order/api/webhooks/fonnte?secret=NILAI_SECRET`
4. Riwayat dan tombol Kirim Ulang ada di menu Notifikasi WA. Kegagalan Fonnte tidak membatalkan order, pembayaran, maupun pengiriman.

## 8. Checklist verifikasi di VPS
```bash
curl -sI https://relaylab.id/order | grep -i location        # → /order/
curl -s  https://relaylab.id/order/api/health                # {"status":"ok"}
curl -sI https://relaylab.id/order/admin/orders | head -1    # 200 (refresh SPA)
curl -s  https://relaylab.id/order/ | grep -o '/order/static/js/[^"]*'   # aset ber-prefix /order
curl -s -X POST https://relaylab.id/order/api/webhooks/fonnte -H 'Content-Type: application/json' -d '{"sender":"620000","message":"halo"}'   # {"status":true}
ss -tlnp | grep -E '8100|8101|27017'    # 8100/8101 hanya 127.0.0.1, 27017 tidak muncul di host
```
Uji persistensi (Pengujian 8):
1. Login, buat order, lalu buat pengiriman dengan foto resi.
2. Jalankan `docker compose down && docker compose up -d`.
3. Pastikan order, pembayaran, dan foto resi masih tampil. `ls data/uploads/resi` harus menunjukkan file foto.

Pastikan juga `https://relaylab.id/` dan `https://relaylab.id/presensi/` tetap normal.

## Catatan keamanan
- Token Fonnte dan kredensial database hanya ada di `.env` server, tidak pernah dikirim ke frontend.
- Cookie `httpOnly` + `Secure` + `SameSite=Lax`, dengan path `/order` dan proteksi CSRF. Wajib HTTPS (`COOKIE_SECURE=true`).
- Password di-hash dengan Argon2id. Login dikunci 15 menit setelah 5 kali gagal.
- MongoDB tidak punya port publik. Firewall cukup membuka 22, 80, dan 443 (`sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable`). Catatan: Docker tidak membypass UFW di sini karena port OMS hanya terikat ke 127.0.0.1.
