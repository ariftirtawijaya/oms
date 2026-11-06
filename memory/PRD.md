# RelayLab OMS — PRD

## Original problem statement
RelayLab Order Management System (RelayLab OMS): B2B order management website between RelayLab Autolight (automotive relay set manufacturer) and its resellers. Not a public marketplace; account-only access. Roles: Admin (dashboard, products, resellers, login users, orders on behalf of resellers, status, production progress, payments, shipments + receipt photos, transaction history, reports, Special Reseller, WhatsApp notification log) and Reseller (own dashboard, catalog, create order, custom products, order list/detail, progress, payments, shipments, receipt photos, order recap, profile). All UI in Bahasa Indonesia. Must be self-hostable on own VPS (Docker Compose, Nginx+HTTPS, MongoDB persistent volume, local file storage /data/uploads/resi, /data/uploads/products, .env.example, backup/restore docs). Critical: PRICE SNAPSHOT (master price changes never affect existing orders, payments, reports), product price history, per-order price adjustment with audit, min qty 10 pcs (regular) / 1 pcs (Special Reseller) validated front+back without losing the cart, custom products priced later by admin, order code RL-DDMMYY-0001 (Asia/Jakarta, concurrency-safe), statuses menunggu_konfirmasi/diproses/selesai separate from payment status, partial payments + corrections, partial shipments with auto Selesai, Fonnte WhatsApp notifications via outbox (failures never cancel transactions, retry), webhook /api/webhooks/fonnte with /cekorder, /pengumuman (+/batal, whitelist, timeout, dedupe), no auto reply to normal messages, reseller recap by date range + CSV, admin financial reports, security (Argon2id, sessions, CSRF, rate limit, upload validation, audit logs, double-submit prevention, reseller data isolation in backend).

User choices: WhatsApp queued/simulated until FONNTE_TOKEN set (WHATSAPP_MODE=simulation|live); NO migration from old PHP/MySQL (fresh DB); Super Admin seeded from env; Argon2id; must-change-password option for temporary passwords; custom-price orders may be set to Diproses anytime; app must be fully functional, mobile-first, 100% self-hosted.

## Architecture
- Backend: FastAPI modular (`backend/app/`: config, db (indexes), security (Argon2id, JWT httpOnly cookies, CSRF double-submit, roles), schemas, utils, services/orders (snapshot, counter, versioned updates), services/notifications (Fonnte httpx, outbox worker, retry/backoff, media fallback), services/storage (magic-byte validated uploads), routes: auth, products, resellers(+users), orders(+files), reports(+dashboard), notifications(+audit, webhook)).
- MongoDB collections: users, resellers, products (embedded price_history), orders (embedded items with snapshots, price_adjustments, status_history, version), order_payments, shipments, notification_logs, announcement_states (TTL), system_settings (daily order counters), audit_logs, login_attempts, webhook_events (TTL).
- Frontend: React + TypeScript (CRA/craco, type-check plugin disabled in dev), Tailwind, shadcn/ui, TanStack Query, TanStack Table v8, RHF + Zod, Recharts.
- Deploy: `/app/deploy` (docker-compose with mongo/backend/frontend/nginx/certbot, nginx template, .env.example, backup.sh/restore.sh, README_DEPLOY.md). `backend/requirements.prod.txt` + Dockerfiles (frontend build strips Emergent dev packages).

## Implemented (2026-11-05)
- Auth: login/logout/refresh/me/change-password, forced password change, brute-force lockout (5 fails/15 min) + IP limiter, token_version session revocation, Super Admin protected.
- Products CRUD + price history; Resellers CRUD + Special flag + optional login; Users management (create/reset/deactivate).
- Reseller marketplace order page: 8/page catalog, token search, card cart persisted in localStorage, custom product modal, min-qty validation (front+back), price-change detection + 409 PRICE_CHANGED, idempotent submit.
- Admin order creation on behalf of reseller (searchable dropdowns).
- Order detail (admin & reseller): snapshot items, unfinished/finished items, progress, payments (+void/correction, overpay), shipments multipart with receipt photo, price adjustment, custom resolve/mapping, internal notes, status history, auto Selesai.
- Dashboards (admin w/ charts, reseller), Rekap Order w/ CSV, admin reports (per reseller + cashflow) w/ CSV, notification log w/ retry, audit log.
- Fonnte outbox (simulation mode in dev), webhook commands.
- Testing: iteration_1 — backend 14/14, frontend flows all pass; follow-ups fixed (date pickers DD-MM-YYYY, super admin protection, idempotency scoped per order, shipment insert-before-update, client IP, webhook dedupe, mobile sheet overlap, special min-qty race).

## Implemented (2026-11-05, iteration 2–3)
- Verified multiple payments & shipments per order; idempotency only blocks same request (per-order scoped, ref-based click lock).
- TypeScript strict check: `yarn typecheck` (tsc --noEmit, 0 errors); Docker build runs `yarn build:prod` (typecheck + build). TS 5.6, allowJs off.
- 24h JJ:MM time input + DD-MM-YYYY calendar pickers; Indonesian file picker; no 4xx retries; wider layout; title-case headers.
- Production index.html (public/index.prod.html) without dev scripts/analytics; Dockerfile strips @emergentbase dev packages.
- Tests: iteration_2 backend 20/20 + UI; iteration_3 UI fixes 100%. Test data wiped afterwards.

## Implemented (2026-11-05, iteration 4 — VPS multi-project /order/)
- React Router basename + asset base from PUBLIC_URL (/order); API = ${REACT_APP_BACKEND_URL}/api; COOKIE_PATH env (/order).
- docker-compose without 80/443/nginx/certbot: frontend 127.0.0.1:8100, backend 127.0.0.1:8101, Mongo internal only (WiredTiger cache 0.25 GB, mem limits ~1 GB total, log rotation).
- deploy/nginx/relaylab.id.conf.example (host nginx: /order/ and /order/api/ blocks, prefix stripped once), README_DEPLOY.md rewritten for multi-project.
- Verified via local nginx simulation of /order (iteration_4: 100%, no /order/api/api, cookies Path=/order) + preview regression 20/20.

## Implemented (2026-11-06, iteration 5 — UI revision)
- Product code removed from UI/API (form: name, price ≥1 required, voltage select 12/24/-, notes, active); unique code index dropped; legacy code fields tolerated.
- Catalog cards show full names, equal-height cards, bottom-aligned price/button; SearchSelect wraps long names.
- Order items accordion (collapsed: name, qty, subtotal / "Harga Belum Ditentukan"; expanded details; admin actions inside).
- Standard Pager (10/20/50/100, localStorage per list) for all tables, catalog, items, payments, shipments; orders list server-side paginated (page/limit/q/status/payment_status/date/sort).
- Reseller UI: no Special labels (API exposes min_qty instead of is_special), no snapshot wording, Order Saya without subtitle.
- iteration_5: backend 27/27, frontend pass (tester fixed orders paging bug; low issues fixed after).

## Implemented (2026-11-06, iteration 6 — production readiness)
- frontend/yarn.lock tracked; Dockerfile uses `yarn install --frozen-lockfile`; .dockerignore excludes .env*.
- Same-origin API: api.ts falls back to `${PUBLIC_URL}/api` (= /order/api) when REACT_APP_BACKEND_URL is absent (production build); compose no longer passes REACT_APP_BACKEND_URL.
- deploy/.env.example + backend/.env.example tracked (`!.env.example` in .gitignore); backend/data/, deploy/data/, deploy/backups/, **/uploads/ ignored; committed test resi photo untracked.
- Nginx: deploy/nginx/relaylab-oms-upstream.conf (conf.d) + relaylab-oms-locations.conf (snippet, `include` in existing HTTP/HTTPS server blocks); README_DEPLOY rewritten for landing `/` + `/stock/` PHP 8.4 + MariaDB 10.11, IP 103.247.9.189.
- Tested locally (no Docker in agent env): clean frozen install, prod build, nginx emulation, auth/order/payment/shipment/upload/restart persistence, Fonnte simulation.


## Implemented (2026-11-06, iteration 7 — pagination, branding, data cleanup, "anda")
- Reseller order detail: Item Belum Selesai / Item Selesai paginated independently (5/10/20/50/100, default 5, localStorage keys reseller-unfinished-items / reseller-finished-items); Pager/usePager got optional `sizes` (other pages unchanged 10/20/50/100).
- Pengaturan (/admin/settings): Branding tab (name, tagline, logo PNG/JPG/WebP ≤2MB, favicon PNG/ICO ≤1MB; system_settings _id=branding; files UPLOAD_DIR/branding with uuid names; public GET /api/branding(+/files); admin PUT /api/settings/branding, POST reset) applied to sidebar, mobile header/nav, login, title, favicon (lib/branding.tsx BrandingHead/BrandMark).
- Pembersihan Data tab (Super Admin only): categories orders/resellers/products/notifications/audit, optional order_seq reset, preview counts + blocking/warnings, HAPUS DATA + password, verified jsonl backup to BACKUP_DIR (compose ./backups/app:/data/backups, 0700/0600) before delete, delete by backed-up _ids, auto-restore on failure, pending order WA → cancelled, maintenance flag (writes 503, worker paused), permanent security_logs, manual restore `python -m app.restore_cleanup <folder>` (restored pending WA → cancelled, duplicate conflicts skipped).
- "Anda" mid-sentence → "anda" (UI, backend messages, WA reply).
- Tested on isolated QA stack (prod build at 127.0.0.1:8088/order, mongod 27018): iteration_6 backend 26/26 new + 27/27 regression, frontend flows 100%.

## Implemented (2026-11-07, iteration 8 — refinements)
- Reseller order detail polling 20s (only while tab visible) + refetch on focus; pagination prefs kept, page clamps.
- Compact Pager variant for the two narrow reseller sections (count+select row, centered icon nav).
- Cleanup rollback: auto-restore exact (pending WA kept), verify_restore compares every backed-up doc + resi SHA-256; unverified → clear 500 message, backup kept, security log gagal_pemulihan_otomatis. Test-only env CLEANUP_TEST_FAIL_AFTER / CLEANUP_TEST_FAIL_RESTORE (never set in production). CLI restore verifies content + hashes, non-zero exit if incomplete.
- Docs/scripts: sudo docker compose everywhere, backup.sh/restore.sh self-elevate with sudo, cron in root crontab.
- iteration_7: rollback 6 fault points identical snapshot diff, 38/38 backend, frontend checks 100%.

## Implemented (2026-11-07, iteration 9 — cleanup crash safety & integrity)
- Any resi unlink failure = failure → restore DB + photos from backup + verify (no more berhasil_sebagian_file).
- Persistent journal system_settings._id=cleanup_lock (backup → deleting → done | rolling_back → needs_manual); recover_on_startup: backup→cancel (partial folder renamed INCOMPLETE-*), done→log, deleting/rolling_back/needs_manual→integrity check + restore + verify, else block all writes (503, login allowed), WA worker paused, admin MaintenanceBanner + GET /api/settings/cleanup/status; cleanup controls disabled while blocked.
- Backup streamed per 500-doc batch with SHA-256 while writing + re-hash + re-parse; photos SHA-256; manifest.json (sha/count/files, complete). Restore/verify iterate manifest only, batched; deletes by _id chunks 1000.
- CLI restore_cleanup: integrity → restore → verify (content + SHA) → closes matching journal, logs dipulihkan_manual; restart backend to unblock.
- Test-only env: CLEANUP_TEST_FAIL_AFTER (collection|resi_files|resi_unlink), CLEANUP_TEST_FAIL_RESTORE, CLEANUP_TEST_DELAY — never in production.
- iteration_8/9: crash suite 10/10 (×3 runs), delta 4/4, regression pass; kill -9 during backup/deleting verified with full snapshot diff.

## Implemented (2026-11-07, iteration 10-11 — journal/middleware/streaming audit fixes)
- Journal cleanup_lock deleted only when certain (drain timeout/backup failure before deletion, done, verified rollback). Cancellation/unexpected exception → journal kept, writes blocked ("memulihkan otomatis"), background recover_journal(source=cancel) → 'dipulihkan_setelah_dibatalkan' or needs_manual; wrapper never leaves it stuck.
- Middleware: during active/blocked only /api/auth/login|logout|refresh; login skips last_login_at; blocked 503 generic for everyone (backup id only in admin banner via /api/settings/cleanup/status). In-flight writes + WA process_one counted (STATE.inflight); execute drains ≤30s before backup.
- Streaming v2 backup: no in-RAM id lists; files.jsonl (name, sha256); manifest version 2; deletion reads id batches of 1000 from verified backup; folders 0700 (files/ too).
- Test-only: CLEANUP_TEST_FAIL_AFTER also supports backup, end, cancel:<point> (real task.cancel()).
- QA tooling persisted in /app/memory/qa/ (be.env, seed.py, nginx.conf).
- iteration_10/11: 34/34 QA backend tests (cancel ×4 points, kill -9, bg-failure, 20k scale RSS 66–92 MB, 60 concurrent writes race) + UI flows.

## Backlog
- P1: Server-side pagination for orders/dashboard when data grows; set FONNTE_WEBHOOK_SECRET in production.
- P1: Product images (uploads/products dir prepared), separate admin page for WhatsApp admin whitelist.
- P2: Excel (.xlsx) export, payment notification to reseller, MongoDB replica set + transactions.

## Next tasks
- User deploys to VPS following deploy/README_DEPLOY.md, fills Fonnte credentials, switches WHATSAPP_MODE=live.
