# RelayLab OMS — Panduan Deployment VPS (Self-Hosted)

Aplikasi berjalan 100% di VPS Anda: Nginx (HTTPS) → React (frontend) + FastAPI (backend) → MongoDB + penyimpanan file lokal → Fonnte WhatsApp API. Tidak ada ketergantungan ke layanan hosting/storage Emergent.

```
deploy/
├── docker-compose.yml
├── .env.example            → salin menjadi .env
├── nginx/relaylab.conf.template
├── nginx/bootstrap-http.conf.template
├── scripts/backup.sh
├── scripts/restore.sh
└── data/                   → dibuat otomatis (PERSISTENT)
    ├── mongo/              → database MongoDB
    └── uploads/resi/       → foto resi
        uploads/products/
```

## 1. Persiapan VPS
- Ubuntu 22.04/24.04, minimal 2 GB RAM.
- Install Docker & Compose plugin: `curl -fsSL https://get.docker.com | sh`
- Arahkan DNS domain (A record) ke IP VPS. Buka port 80 dan 443.

## 2. Salin source code & konfigurasi
```bash
git clone <repo-anda> /opt/relaylab && cd /opt/relaylab/deploy
cp .env.example .env
nano .env        # isi DOMAIN, PUBLIC_URL, password MongoDB, JWT_SECRET (openssl rand -hex 32), ADMIN_EMAIL, ADMIN_PASSWORD
mkdir -p data/mongo data/uploads/resi data/uploads/products backups certbot/www certbot/conf
sudo chown -R 1000:1000 data/uploads
chmod +x scripts/*.sh
```

## 3. Sertifikat HTTPS pertama kali (Let's Encrypt)
```bash
# a) Jalankan nginx sementara mode HTTP saja
cp nginx/relaylab.conf.template nginx/relaylab.conf.template.bak
cp nginx/bootstrap-http.conf.template nginx/relaylab.conf.template
docker compose up -d nginx
# b) Minta sertifikat
docker compose run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
  -d "$(grep ^DOMAIN= .env | cut -d= -f2)" --email emailanda@domain.com --agree-tos --no-eff-email
# c) Kembalikan konfigurasi HTTPS
mv nginx/relaylab.conf.template.bak nginx/relaylab.conf.template
```

## 4. Jalankan aplikasi
```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```
Buka `https://DOMAIN-ANDA`, login memakai `ADMIN_EMAIL` / `ADMIN_PASSWORD`. Akun Super Admin hanya dibuat sekali saat belum ada; mengubah `.env` setelahnya tidak menimpa password yang sudah diganti di aplikasi. Segera ganti password lewat menu **Ganti Password**.

## 5. Update aplikasi (tanpa kehilangan data)
```bash
cd /opt/relaylab && git pull && cd deploy
./scripts/backup.sh
docker compose up -d --build
```
Database (`data/mongo`) dan foto (`data/uploads`) berada di folder host, sehingga tetap ada walaupun kontainer di-restart, dihapus (`docker compose down`), atau dibangun ulang.

## 6. Backup & Restore
```bash
./scripts/backup.sh                          # hasil di deploy/backups/
./scripts/restore.sh backups/mongo-YYYYMMDD-HHMMSS.archive.gz backups/uploads-YYYYMMDD-HHMMSS.tar.gz
```
Backup otomatis harian (crontab -e):
```
0 2 * * * cd /opt/relaylab/deploy && ./scripts/backup.sh >> backups/backup.log 2>&1
```
Salin folder `backups/` ke lokasi lain (mis. rclone ke Google Drive/NAS) secara berkala.

## 7. WhatsApp Fonnte
1. Isi `FONNTE_TOKEN`, `FONNTE_ADMIN_WA` (boleh beberapa, pisahkan koma — juga menjadi whitelist `/pengumuman`), `FONNTE_GROUP_ID`.
2. Ubah `WHATSAPP_MODE=live`, lalu `docker compose up -d backend`.
3. Di dashboard Fonnte, set URL webhook perangkat ke: `https://DOMAIN-ANDA/api/webhooks/fonnte` (jika `FONNTE_WEBHOOK_SECRET` diisi, tambahkan `?secret=NILAI`).
4. Command yang didukung: `/cekorder KODE`, `/pengumuman` (admin), `/batal`. Pesan lain tidak dibalas sehingga CS manual tidak terganggu.
5. Pengiriman foto resi memerlukan paket Fonnte yang mendukung lampiran. Jika gagal, sistem otomatis mengirim teks tanpa kalimat "Foto resi terlampir".
6. Riwayat, error, dan tombol **Kirim Ulang** ada di menu **Notifikasi WA**. Notifikasi gagal dicoba ulang otomatis (1, 5, 15, 60 menit, maks 5 kali). Kegagalan Fonnte tidak pernah membatalkan order/pembayaran/pengiriman.

## 8. Pengujian self-hosted (Pengujian 8)
```bash
# upload foto resi lewat admin → buat pengiriman, lalu:
docker compose down && docker compose up -d
ls data/uploads/resi      # file masih ada
```
Login kembali dan pastikan order, pembayaran, dan foto resi masih tampil.

## 9. Menghapus data uji
Semua data uji dari pengembangan tidak ikut ke VPS (database VPS dimulai kosong). Jika Anda membuat data uji di VPS, beri awalan `TEST_` pada nama reseller/produk lalu hapus via mongosh:
```bash
docker compose exec mongo mongosh -u $MONGO_ROOT_USER -p --authenticationDatabase admin relaylab_oms
```

## Catatan keamanan
- Token Fonnte & kredensial database hanya ada di `.env` server, tidak pernah dikirim ke frontend.
- Cookie sesi `httpOnly` + `Secure` + proteksi CSRF (double-submit token); wajib HTTPS (`COOKIE_SECURE=true`).
- Password di-hash dengan Argon2id. Login dikunci 15 menit setelah 5 percobaan gagal.
- MongoDB tidak dipublikasikan ke internet (hanya jaringan internal Docker).
