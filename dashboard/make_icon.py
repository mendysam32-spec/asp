"""Generate a 1024x1024 app icon for the TikTok developer app."""
from PIL import Image, ImageDraw, ImageFont

SIZE = 1024
img = Image.new("RGB", (SIZE, SIZE))
d = ImageDraw.Draw(img)

# Dark gradient-ish background (bands for simplicity)
for y in range(SIZE):
    # Deep navy -> purple gradient
    t = y / SIZE
    r = 20 + int(100 * t)
    g = 20 + int(30 * t)
    b = 90 + int(120 * t)
    d.line([(0, y), (SIZE, y)], fill=(r, g, b))

# Central rounded emblem
cx, cy = SIZE // 2, SIZE // 2
side = 460
x0, y0, x1, y1 = cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2
d.rounded_rectangle([x0, y0, x1, y1], radius=100, fill=(255, 255, 255))

# "T-R" monogram
try:
    font = ImageFont.truetype("arialbd.ttf", 200)
except Exception:
    font = ImageFont.load_default()

text = "TR"
bbox = d.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
d.text((cx - tw / 2, cy - th / 2 - 10), text, font=font, fill=(40, 40, 90))

# Tagline accent bar
d.rounded_rectangle(
    [cx - 130, cy + 150, cx + 130, cy + 178],
    radius=14,
    fill=(235, 87, 87),
)

out = r"C:\Users\kumen\ai-agent\dashboard\app_icon.png"
img.save(out, "PNG")
print(f"Saved: {out}")
print(f"Size: {img.size}")