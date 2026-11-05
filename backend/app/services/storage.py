import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app import config

SIGNATURES = {
    "jpg": lambda b: b[:3] == b"\xff\xd8\xff",
    "png": lambda b: b[:8] == b"\x89PNG\r\n\x1a\n",
    "webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def ensure_dirs():
    for sub in ("resi", "products"):
        (config.UPLOAD_DIR / sub).mkdir(parents=True, exist_ok=True)


def resi_path(filename: str) -> Path:
    safe = Path(filename).name
    return config.UPLOAD_DIR / "resi" / safe


async def save_receipt(upload: UploadFile) -> str:
    ext = (upload.filename or "").rsplit(".", 1)[-1].lower() if "." in (upload.filename or "") else ""
    if ext not in ALLOWED_EXT or (upload.content_type or "") not in ALLOWED_MIME:
        raise HTTPException(status_code=422, detail="Format foto resi harus JPG, JPEG, PNG, atau WebP.")
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=422, detail=f"Ukuran foto resi maksimal {config.MAX_UPLOAD_MB} MB.")
    detected = next((k for k, fn in SIGNATURES.items() if fn(data)), None)
    if not detected:
        raise HTTPException(status_code=422, detail="Isi file bukan gambar yang valid.")
    name = f"{uuid.uuid4().hex}.{detected}"
    ensure_dirs()
    resi_path(name).write_bytes(data)
    return name
