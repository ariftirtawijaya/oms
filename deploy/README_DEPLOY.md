# RelayLab OMS — Deployment di VPS RelayLab (/order/)

## Kondisi VPS
| Item | Nilai |
|---|---|
| OS | Ubuntu 24.04 LTS — 2 vCPU, 4 GB RAM + swap 2 GB, 80 GB SSD |
| IP / domain | `103.247.9.189` / `relaylab.id` |
| Web server | Nginx (sudah berjalan) |
| Aplikasi lama | Landing page di `/`, Stock Management PHP 8.4 + MariaDB 10.11 di `/stock/` |
| OMS | React + FastAPI + MongoDB via Docker Compose di `/order/` dan `/order/api/` |

```
Internet ─► Nginx utama VPS (80/443)
              ├─ /            → landing page (TIDAK diubah)
              ├─ /stock/      → PHP-FPM 8.4 ─► MariaDB 10.11 (TIDAK diubah)
              ├─ /order/api/  → 127.0.0.1:8101 ─► [backend FastAPI] ─► [mongo] (jaringan Docker internal)
              └─ /order/      → 127.0.0.1:8100 ─► [frontend nginx statis]
```

Prinsip:
- Docker Compose OMS **tidak memakai port 80/443**. Port OMS hanya terikat ke `127.0.0.1` (8100 frontend, 8101 backend).
- MongoDB **tidak punya port di host**; hanya bisa diakses dari jaringan Docker `relaylab-oms-net`. MariaDB dan PHP tidak disentuh.
- **Same-origin API**: frontend memanggil URL relatif `/order/api/...`. Build yang sama bekerja di `https://103.247.9.189/order/` dan `https://relaylab.id/order/` tanpa build ulang.
- Prefix `/order` hanya dibuang sekali, di Nginx utama. Jangan menambah prefix `/order` di FastAPI.

## 1. Struktur & data persisten
```
/opt/relaylab-oms/            ← git clone repository
└── deploy/
    ├── docker-compose.yml
    ├── .env                  ← dari .env.example (rahasia, diabaikan Git)
    ├── nginx/relaylab-oms-upstream.conf, relaylab-oms-locations.conf
    ├── scripts/backup.sh, restore.sh
    ├── data/mongo/           ← DATABASE MongoDB (bind mount, persisten)
    ├── data/uploads/resi/    ← FOTO RESI (bind mount, persisten)
    └── backups/
```
`deploy/data/` dan `deploy/backups/` diabaikan Git dan tidak terhapus oleh `docker compose down`, rebuild, maupun `git pull`.

Batas memori: mongo 640 MB, backend 320 MB, frontend 64 MB (±1 GB total). Sisanya untuk PHP-FPM, MariaDB, dan Nginx.

## 2. Instalasi pertama
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

sudo git clone https://github.com/ariftirtawijaya/oms.git /opt/relaylab-oms && sudo chown -R $USER /opt/relaylab-oms
cd /opt/relaylab-oms/deploy
cp .env.example .env && chmod 600 .env
nano .env     # ganti MONGO_ROOT_PASSWORD, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD, FONNTE_WEBHOOK_SECRET
```
| Variabel | Nilai | Keterangan |
|---|---|---|
| `OMS_BASE_PATH` | `/order` | Basename React Router, path aset, dan base API (`/order/api`) |
| `COOKIE_PATH` | `/order` | Cookie login hanya berlaku di `/order` |
| `CORS_ORIGINS` | `https://relaylab.id,https://103.247.9.189` | Cadangan; akses same-origin tidak butuh CORS |
| `OMS_FRONTEND_PORT` / `OMS_BACKEND_PORT` | `8100` / `8101` | Port lokal 127.0.0.1 |
| `COOKIE_SECURE` | `true` | Wajib, karena diakses via HTTPS |

```bash
mkdir -p data/mongo data/uploads/resi data/uploads/products backups
sudo chown -R 1000:1000 data/uploads        # user kontainer backend (uid 1000)
chmod +x scripts/*.sh
docker compose config -q                    # validasi compose + .env
docker compose up -d --build                # build pertama ±5–10 menit
docker compose ps
curl -s http://127.0.0.1:8101/api/health    # {"status":"ok"}
curl -sI http://127.0.0.1:8100/ | head -1   # HTTP/1.1 200 OK
```
Swap 2 GB yang sudah ada cukup untuk build frontend; jalankan build saat trafik sepi agar `/stock/` tidak melambat.

## 3. Nginx utama (tanpa menimpa vhost yang ada)
Konfigurasi OMS berupa **dua file tambahan + satu baris include**. Blok `location /` (landing) dan `location /stock/` (PHP 8.4) tidak diubah.

```bash
cd /opt/relaylab-oms/deploy
sudo cp /etc/nginx/sites-available/relaylab.id /root/relaylab.id.backup-$(date +%F)   # sesuaikan nama file vhost Anda
sudo cp nginx/relaylab-oms-upstream.conf  /etc/nginx/conf.d/relaylab-oms-upstream.conf
sudo cp nginx/relaylab-oms-locations.conf /etc/nginx/snippets/relaylab-oms.conf
sudo nano /etc/nginx/sites-available/relaylab.id
```
Di dalam **setiap** server block HTTP (`listen 80`) dan HTTPS (`listen 443 ssl`) yang melayani `relaylab.id` dan `103.247.9.189`, tambahkan satu baris (misalnya tepat sebelum `location /stock/`):
```nginx
    include snippets/relaylab-oms.conf;
```
Contoh posisi (ilustrasi, bagian lain tetap seperti milik Anda):
```nginx
server {
    listen 443 ssl;
    server_name relaylab.id www.relaylab.id 103.247.9.189;
    # ... ssl_certificate, root landing page, location / { ... } milik Anda ...

    include snippets/relaylab-oms.conf;     # ← satu-satunya baris baru

    location /stock/ { ... fastcgi_pass unix:/run/php/php8.4-fpm.sock; ... }   # tidak diubah
}
```
Catatan:
- Jika server HTTP (port 80) Anda hanya berisi `return 301 https://...`, baris include di blok HTTP tidak diperlukan.
- Jika IP `103.247.9.189` dilayani server block lain (mis. `default_server`), tambahkan baris include di blok tersebut juga.
- `^~` pada `/order/` memastikan location regex milik `/stock/` (mis. `location ~ \.php$`) tidak menangkap request OMS.

```bash
sudo nginx -t && sudo systemctl reload nginx
```
HTTPS domain: `sudo certbot --nginx -d relaylab.id -d www.relaylab.id` (setelah DNS mengarah ke VPS). Untuk `https://103.247.9.189/order/` gunakan sertifikat yang sudah terpasang di blok IP Anda (self-signed akan memunculkan peringatan browser, tetapi tetap berfungsi untuk pengujian).

Login di `https://relaylab.id/order/` (atau via IP) dengan `ADMIN_EMAIL` / `ADMIN_PASSWORD`, lalu segera ganti password.

## 4. Restart & log
```bash
cd /opt/relaylab-oms/deploy
docker compose restart backend          # setelah mengubah variabel backend di .env
docker compose logs -f --tail=100 backend
docker stats --no-stream
```
`restart: unless-stopped` membuat kontainer hidup lagi setelah VPS reboot.

## 5. Update aplikasi
```bash
cd /opt/relaylab-oms && git pull
cd deploy && ./scripts/backup.sh
docker compose up -d --build
docker image prune -f
```
**Jangan pernah** menjalankan `docker compose down -v` atau menghapus `deploy/data/`.

## 6. Backup & restore
```bash
./scripts/backup.sh
./scripts/restore.sh backups/mongo-XXXX.archive.gz backups/uploads-XXXX.tar.gz
```
Cron harian 02:00 (`crontab -e`):
```
0 2 * * * cd /opt/relaylab-oms/deploy && ./scripts/backup.sh >> backups/backup.log 2>&1
```
Backup MariaDB `/stock/` tetap dilakukan terpisah (mysqldump) dan tidak terpengaruh OMS.

## 7. WhatsApp Fonnte
1. Isi `FONNTE_TOKEN`, `FONNTE_ADMIN_WA`, `FONNTE_GROUP_ID`, `FONNTE_WEBHOOK_SECRET`.
2. Ubah `WHATSAPP_MODE=live`, lalu `docker compose up -d backend`.
3. URL webhook di dashboard Fonnte: `https://relaylab.id/order/api/webhooks/fonnte?secret=NILAI_SECRET`
4. Selama `WHATSAPP_MODE=simulation`, pesan hanya dicatat di menu Notifikasi WA (tidak dikirim).

## 8. Checklist verifikasi di VPS
```bash
D=https://relaylab.id     # atau https://103.247.9.189 (tambahkan -k bila self-signed)
curl -sI $D/order | grep -i location                         # → /order/
curl -s  $D/order/api/health                                 # {"status":"ok"}
curl -sI $D/order/admin/orders | head -1                     # 200 (refresh SPA, bukan 404)
curl -s  $D/order/ | grep -o '/order/static/js/[^"]*'        # aset ber-prefix /order
curl -sI $D/ | head -1 ; curl -sI $D/stock/ | head -1        # landing & stock tetap normal
ss -tlnp | grep -E '8100|8101|27017'                         # 8100/8101 hanya 127.0.0.1, 27017 tidak ada
```
Uji persistensi: buat order + pembayaran + pengiriman dengan foto resi → `docker compose down && docker compose up -d` → data dan foto masih tampil, `ls data/uploads/resi` berisi file.

## Catatan keamanan
- Token Fonnte, password MongoDB, dan JWT secret hanya ada di `deploy/.env` (diabaikan Git, `chmod 600`).
- Cookie `httpOnly` + `Secure` + `SameSite=Lax`, path `/order`, dengan proteksi CSRF.
- Password Argon2id; login dikunci 15 menit setelah 5 kali gagal.
- Firewall: `sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable`. Port OMS hanya 127.0.0.1, MongoDB tanpa port host.
