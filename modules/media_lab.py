"""Media Lab - turns agent scripts into real vertical media.

Pipeline: script text -> styled quote cards (Pillow) -> narrated 9:16 MP4 (ffmpeg + edge-tts).
Used by the autonomous loop so TikTok/Shorts get actual uploadable files, not just text.
"""
import asyncio
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import imageio_ffmpeg

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "data" / "media"

FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

VOICES = ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural",
          "en-US-AriaNeural", "en-US-ChristopherNeural"]


def _font(size: int, bold: bool = False):
    for name in ([r"segoeuib.ttf", r"arialbd.ttf"] if bold else [r"segoeui.ttf", r"arial.ttf"]):
        p = FONT_DIR / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


def sanitize(text: str) -> str:
    """Strip markdown / time markers / bullets from script text for cards & TTS."""
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", text or "")
    t = re.sub(r"\[[0-9:]+\]", "", t)
    t = re.sub(r"\[(hook|main content|summary|cta)\]", "", t, flags=re.I)
    t = re.sub(r"[#*_>`]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or "TheRepublic"


def _wrap(draw, text, font, max_w) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _render_card(text: str, accent: tuple, accent2: tuple, size=(1080, 1920)) -> Image.Image:
    W, H = size
    img = Image.new("RGB", (W, H), (13, 17, 34))
    d = ImageDraw.Draw(img)
    # vertical gradient
    top, bot = (22, 27, 52), (7, 9, 20)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    # soft accent glow
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([(W * 0.32, -H * 0.35), (W * 1.15, H * 0.45)], fill=accent)
    gd.ellipse([(-W * 0.35, H * 0.55), (W * 0.55, H * 1.3)], fill=accent2)
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    img = Image.blend(img, glow, 0.55)

    d = ImageDraw.Draw(img)
    # top accent bar
    d.rounded_rectangle([(W * 0.08, H * 0.06), (W * 0.92, H * 0.062 + 6)], radius=3, fill=accent2)
    # watermark
    small = _font(46, bold=True)
    d.text((W * 0.08, H * 0.075), "TheRepublic", font=small, fill=(255, 255, 255))

    body = _wrap(d, text, _font(76 - (len(text) // 14), bold=True), W * 0.84)
    body = body[:6]
    y = H * 0.40 - (len(body) * 108) / 2
    for i, line in enumerate(body):
        alpha = 1.0 - (i * 0.05)
        color = tuple(int(c * alpha) for c in (255, 255, 255))
        d.text((W * 0.08, y), line, font=_font(76 - (len(text) // 14), bold=True), fill=color)
        y += 112
    # footer bar
    if body:
        d.rounded_rectangle([(W * 0.08, y + 26), (W * 0.92, y + 30)], radius=3, fill=accent)
    d.text((W * 0.08, H * 0.94), "grow with the machine", font=_font(40), fill=(160, 168, 210))
    return img


def _segments_from_text(text: str, max_lines: int = 6) -> List[str]:
    """Split a script into punchy card segments: hook, points, CTA."""
    t = sanitize(text)
    lines = [l.strip() for l in t.split(".") if l.strip()]
    if len(lines) <= 2:
        parts = t.split(",")
        return [p.strip()[:150] for p in parts if p.strip()][:max_lines] or [t[:150]]
    segs = lines[:max_lines]
    first = segs[0][:110]
    rest = [s[:140] for s in segs[1:] if s]
    # cut out redundant intro like "TITLE" artefacts
    if rest and ("description" in rest[0].lower() or "keywords" in rest[0].lower()):
        rest = rest[1:]
    out = [first] + rest
    # drop near-duplicate consecutive cards so the video doesn't repeat itself
    deduped = []
    for s in out:
        if not deduped or s.lower() != deduped[-1].lower():
            deduped.append(s)
    return deduped[:max_lines] or [t[:150]]


async def _synth_audio(text: str, voice: str, out_path: Path) -> bool:
    try:
        import edge_tts
        if voice not in VOICES:
            voice = VOICES[0]
        comm = edge_tts.Communicate(sanitize(text), voice)
        await comm.save(str(out_path))
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception as e:
        print(f"[Media] TTS failed: {e}")
        return False


def _probe_duration(path: Path) -> float:
    try:
        r = subprocess.run([FFMPEG, "-i", str(path), "-f", "null", "-"],
                           capture_output=True, text=True, timeout=60)
        for line in r.stderr.splitlines():
            m = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
            if m:
                h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                return h * 3600 + mnt * 60 + s
    except Exception:
        pass
    return 0.0


def _render_clip(card: Image.Image, seconds: float, out_path: Path) -> bool:
    tmp = MEDIA_DIR / f"card_{out_path.stem}.png"
    card.save(tmp)
    fps = 30
    frames = int(seconds * fps)
    vf = (
        "[0:v]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
        f"zoompan=z='min(1+0.0007*on,1.12)':d={frames}:s=1080x1920:fps={fps},format=yuv420p[v]"
    )
    cmd = [FFMPEG, "-y", "-i", str(tmp), "-filter_complex", vf,
           "-map", "[v]", "-c:v", "libx264", "-preset", "fast", "-t", f"{seconds:.2f}",
           str(out_path)]
    try:
        subprocess.run(cmd, capture_output=True, timeout=300)
        tmp.unlink(missing_ok=True)
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception as e:
        print(f"[Media] clip render failed: {e}")
        tmp.unlink(missing_ok=True)
        return False


async def render(text: str, accent="#6c5ce7", accent2="#00d2ff", voice: Optional[str] = None,
                 slug: Optional[str] = None) -> Dict:
    """Render script text -> quote card PNG + narrated 9:16 MP4. Returns paths dict."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    slug = (slug or "post").replace(" ", "_").replace("/", "_")[:40]
    stamp = __import__("datetime").datetime.now().strftime("%H%M%S")
    tag = f"{slug}_{stamp}"

    acc = (108, 92, 231)
    try:
        acc = tuple(int(accent.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        pass

    segments = _segments_from_text(text)
    cards = [_render_card(s, acc, (0, 210, 255)) for s in segments]

    image_path = MEDIA_DIR / f"{tag}.png"
    cards[0].save(image_path)

    video_path = MEDIA_DIR / f"{tag}.mp4"
    result = {"image": str(image_path), "video": None, "segments": segments,
              "error": None, "audio": False, "card": str(image_path)}

    audio_ok, audio_dur = False, 0.0
    if voice is not None:
        audio_path = MEDIA_DIR / f"{tag}.mp3"
        audio_ok = await _synth_audio(text, voice, audio_path)
        audio_dur = _probe_duration(audio_path) if audio_ok else 0.0

    try:
        if audio_ok and audio_dur > 3:
            total = sum(max(3.0, min(11.0, len(s) / 13.0)) for s in segments)
            scale = (audio_dur / total) if total > 0 else 1.0
            durations = [max(2.6, min(12.0, max(3.0, min(11.0, len(s) / 13.0)) * scale))
                         for s in segments]
        else:
            durations = [4.0] * len(segments)

        clips = []
        for i, card in enumerate(cards):
            clip = MEDIA_DIR / f"clip_{tag}_{i}.mp4"
            if _render_clip(card, durations[i], clip) and clip.stat().st_size > 0:
                clips.append(str(clip))
            else:
                print(f"[Media] clip {i} failed; skipping segment")
        if not clips:
            result["error"] = "no clips rendered"
            return result

        listf = MEDIA_DIR / f"list_{tag}.txt"
        listf.write_text("\n".join(f"file '{c}'" for c in clips), encoding="utf-8")
        concat = MEDIA_DIR / f"concat_{tag}.mp4"
        subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(listf),
                        "-c", "copy", str(concat)], capture_output=True, timeout=300)

        if audio_ok:
            subprocess.run([FFMPEG, "-y", "-i", str(concat), "-i", str(audio_path),
                            "-c:v", "copy", "-c:a", "aac", "-shortest", str(video_path)],
                           capture_output=True, timeout=300)
            result["audio"] = True
        else:
            video_path.write_bytes(concat.read_bytes())

        for f in [listf, concat] + clips:
            Path(f).unlink(missing_ok=True)
        if video_path.exists() and video_path.stat().st_size > 0:
            result["video"] = str(video_path)
        else:
            result["error"] = "final mp4 missing"
    except Exception as e:
        result["error"] = f"render failed: {e}"
    return result