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

## Backlog
- P1: Server-side pagination for orders/dashboard when data grows; set FONNTE_WEBHOOK_SECRET in production.
- P1: Product images (uploads/products dir prepared), separate admin page for WhatsApp admin whitelist.
- P2: Excel (.xlsx) export, payment notification to reseller, MongoDB replica set + transactions.

## Next tasks
- User deploys to VPS following deploy/README_DEPLOY.md, fills Fonnte credentials, switches WHATSAPP_MODE=live.
