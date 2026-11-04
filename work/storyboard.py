"""Storyboard: for each EDL clip show first / middle / last source frame exactly as cropped."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
import render as R

TW, TH = 470, 200
OUT = f"{R.WK}/board"
os.makedirs(OUT, exist_ok=True)
edl, clips = R.load_edl()
only = set(int(x) for x in sys.argv[1:]) if len(sys.argv) > 1 else None
FONT = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 17)


def grab(c, k):
    spd = c.get("speed", 1.0)
    d = (c["t1"] - c["t0"]) * spd
    t = c["in"] + [0.05, d / 2, max(0.05, d - 0.08)][k]
    p = f"{OUT}/c{c['idx']:03d}_{k}.jpg"
    x, y, w, h = R.crop_box(c)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", R.SRC[c["src"]]["path"], "-frames:v", "1",
                    "-vf", f"crop={w}:{h}:{x}:{y},scale={TW}:{TH}", "-q:v", "3", p], check=True)
    return p


todo = [c for c in clips if only is None or c["idx"] in only]
with ThreadPoolExecutor(24) as ex:
    list(ex.map(lambda a: grab(*a), [(c, k) for c in todo for k in range(3)]))

PER = 8
for s0 in range(0, len(todo), PER):
    grp = todo[s0:s0 + PER]
    img = Image.new("RGB", (220 + 3 * (TW + 6), len(grp) * (TH + 6)), (20, 20, 20))
    d = ImageDraw.Draw(img)
    for r, c in enumerate(grp):
        y = r * (TH + 6)
        lab = f"#{c['idx']} b{c['b']}\n{c['t0']:.1f}-{c['t1']:.1f}s\n{c['src']} @{c['in']}\n{c.get('note','')}"
        d.multiline_text((6, y + 6), lab, font=FONT, fill=(255, 230, 120), spacing=4)
        for k in range(3):
            im = Image.open(f"{OUT}/c{c['idx']:03d}_{k}.jpg")
            img.paste(im, (220 + k * (TW + 6), y))
    name = f"{OUT}/board_{grp[0]['idx']:03d}.jpg"
    img.save(name, quality=85)
    print(name)
