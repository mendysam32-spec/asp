"""Generate a short, valid MP4 sample video for the TikTok demo."""
import os
import numpy as np
import imageio.v2 as imageio
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUT = r"C:\Users\kumen\ai-agent\dashboard\site\sample.mp4"

W, H, FPS, DURATION = 720, 1280, 30, 3  # vertical video, 9:16

tmp = r"C:\Users\kumen\AppData\Local\Temp\opencode\tiktok_sample.mp4"
writer = imageio.get_writer(tmp, fps=FPS, codec="libx264", quality=6,
                            ffmpeg_params=["-pix_fmt", "yuv420p"])

for i in range(FPS * DURATION):
    t = i / FPS
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    # animated gradient background
    for y in range(H):
        p = y / H
        frame[y, :, 0] = 0
        frame[y, :, 1] = int(20 + 40 * p)
        frame[y, :, 2] = int(140 + 115 * p)
    # moving white bar
    bx = int(W * (0.1 + 0.8 * (t / DURATION)))
    frame[H//3:2*H//3, bx:bx+80] = 255
    writer.append_data(frame)

writer.close()

# Ensure proper size/format, add faststart via ffmpeg remux
final = OUT
os.system(f'"{FFMPEG}" -y -i "{tmp}" -movflags +faststart -vf "format=yuv420p" "{final}"')
print(f"Sample video -> {OUT}")
print(f"Exists: {os.path.exists(OUT)}, Size: {os.path.getsize(OUT)} bytes")