# Flag proses tunggal (uvicorn 1 worker).
# active: cleanup berjalan; blocked: cleanup belum pasti selesai/pulih -> tulis diblokir;
# inflight: jumlah request tulis & pengiriman WA yang sedang berjalan (ditunggu sebelum backup).
STATE = {"active": False, "blocked": None, "inflight": 0}
