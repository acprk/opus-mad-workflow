"""Grab frames from a rendered video at given times and tile them with labels."""
import subprocess, sys
from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
times = [float(x) for x in sys.argv[3:]]
F = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 22)
tiles = []
for t in times:
    p = f"/tmp/probe_{t:.2f}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
                    "-vf", "scale=640:360", p], check=True)
    im = Image.open(p).convert("RGB")
    ImageDraw.Draw(im).text((8, 4), f"{t:.2f}s", font=F, fill=(255, 220, 0))
    tiles.append(im)
cols = 3
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 644, rows * 364), (40, 40, 40))
for i, im in enumerate(tiles):
    sheet.paste(im, ((i % cols) * 644, (i // cols) * 364))
sheet.save(out, quality=88)
print(out)
