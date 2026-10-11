"""Media editing tools - image basics + video trim/thumbnail.

Image (Pillow, already a dependency):
  - resize (max w/h), crop (x,y,w,h), rotate, grayscale, text overlay
Video (ffmpeg via imageio-ffmpeg, already a dependency):
  - trim (start/end seconds), thumbnail (single jpg at timestamp)
All outputs land in data/media/ with a new filename, never overwriting source.
"""
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

import imageio_ffmpeg

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "data" / "media"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

ALLOWED_IMG = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VID = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


def _resolve(filename: str) -> Path:
    p = Path(filename)
    if not p.is_absolute():
        # allow bare filename or data/media/xxx
        if p.parent == Path("."):
            p = MEDIA_DIR / p.name
        elif str(p).startswith("data/"):
            p = BASE_DIR / p
    # traversal guard: must stay inside MEDIA_DIR
    try:
        p.resolve().relative_to(MEDIA_DIR.resolve())
    except Exception:
        raise ValueError("File must be inside data/media")
    if not p.exists():
        raise FileNotFoundError(f"Not found: {p.name}")
    return p


def _out_name(src: Path, suffix: str) -> Path:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    return MEDIA_DIR / f"{src.stem}_edit{uuid.uuid4().hex[:6]}{suffix}"


def edit_image(filename: str, operation: str, **kw) -> Dict:
    """operation: resize|crop|rotate|grayscale|text|flip"""
    src = _resolve(filename)
    if src.suffix.lower() not in ALLOWED_IMG:
        raise ValueError(f"Not an image: {src.suffix}")
    img = Image.open(src).convert("RGB")
    op = (operation or "").lower()

    if op == "resize":
        w = int(kw.get("width") or img.width)
        h = int(kw.get("height") or img.height)
        max_side = int(kw.get("max_side") or 0)
        if max_side and (w > max_side or h > max_side):
            img.thumbnail((max_side, max_side), Image.LANCZOS)
        else:
            w = max(1, min(w, 4096))
            h = max(1, min(h, 4096))
            img = img.resize((w, h), Image.LANCZOS)
    elif op == "crop":
        x, y = max(0, int(kw.get("x") or 0)), max(0, int(kw.get("y") or 0))
        w, h = int(kw.get("width") or 0), int(kw.get("height") or 0)
        if w <= 0 or h <= 0:
            raise ValueError("crop needs width/height > 0")
        img = img.crop((x, y, min(x + w, img.width), min(y + h, img.height)))
    elif op == "rotate":
        img = img.rotate(float(kw.get("degrees") or 90), expand=True)
    elif op == "grayscale":
        img = ImageOps.grayscale(img).convert("RGB")
    elif op == "flip":
        img = ImageOps.mirror(img) if str(kw.get("direction", "h")).lower().startswith("h") else ImageOps.flip(img)
    elif op == "text":
        text = str(kw.get("text") or "")[:200]
        if not text:
            raise ValueError("text overlay needs {text}")
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(str(Path(r"C:\Windows\Fonts\arialbd.ttf")), int(kw.get("size") or 64))
        except Exception:
            font = ImageFont.load_default()
        pos = str(kw.get("position") or "bottom").lower()
        # simple centered placement
        bbox = d.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x = (img.width - tw) // 2
        y = img.height - 140 if pos == "bottom" else 60 if pos == "top" else img.height // 2
        # shadow box
        d.rectangle([(x - 16, y - 10), (x + tw + 16, y + (bbox[3] - bbox[1]) + 10)], fill=(0, 0, 0))
        d.text((x, y), text, font=font, fill=(255, 255, 255))
    else:
        raise ValueError(f"Unknown image operation: {operation}")

    dst = _out_name(src, ".jpg")
    img.save(dst, "JPEG", quality=92)
    return {"file": str(dst), "filename": dst.name, "preview_url": f"/media/{dst.name}",
            "size": dst.stat().st_size, "operation": op}


def trim_video(filename: str, start: float = 0, end: Optional[float] = None,
               duration: Optional[float] = None) -> Dict:
    """Trim video with ffmpeg stream copy. start/end in seconds."""
    src = _resolve(filename)
    if src.suffix.lower() not in ALLOWED_VID:
        raise ValueError(f"Not a video: {src.suffix}")
    start = max(0.0, float(start or 0))
    if duration is not None:
        dur = max(0.5, float(duration))
    elif end is not None:
        dur = max(0.5, float(end) - start)
    else:
        raise ValueError("Provide end or duration (seconds)")
    dst = _out_name(src, ".mp4")
    cmd = [FFMPEG, "-y", "-ss", str(start), "-i", str(src),
           "-t", str(dur), "-c", "copy", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if not dst.exists() or dst.stat().st_size < 10 * 1024:
        raise RuntimeError(f"Trim failed: {(r.stderr or '')[-400:]}")
    return {"file": str(dst), "filename": dst.name, "preview_url": f"/media/{dst.name}",
            "size": dst.stat().st_size, "start": start, "duration": dur}


def video_thumbnail(filename: str, at: float = 1.0) -> Dict:
    src = _resolve(filename)
    if src.suffix.lower() not in ALLOWED_VID:
        raise ValueError(f"Not a video: {src.suffix}")
    dst = _out_name(src, ".jpg")
    cmd = [FFMPEG, "-y", "-ss", str(max(0.0, float(at or 0))), "-i", str(src),
           "-frames:v", "1", "-q:v", "3", str(dst)]
    subprocess.run(cmd, capture_output=True, timeout=120)
    if not dst.exists() or dst.stat().st_size == 0:
        raise RuntimeError("Thumbnail extraction failed")
    img = Image.open(dst).convert("RGB")
    img.thumbnail((1080, 1080), Image.LANCZOS)
    img.save(dst, "JPEG", quality=90)
    return {"file": str(dst), "filename": dst.name, "preview_url": f"/media/{dst.name}",
            "size": dst.stat().st_size}
