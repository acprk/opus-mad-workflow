"""Index sources: short ids, scene cuts, timestamped contact sheets (every 2 s)."""
import json, os, re, subprocess
from concurrent.futures import ThreadPoolExecutor

from paths import ROOT
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SRC = sorted(os.path.join(ROOT, d, f) for d in ("src", "extra") if os.path.isdir(os.path.join(ROOT, d))
             for f in os.listdir(os.path.join(ROOT, d)) if f.endswith(".mp4"))
SRC = [p for p in SRC if not p.endswith("/牡丹亭外.mp4")]  # static album art, audio only
OUT = os.path.join(ROOT, "work", "index")
os.makedirs(OUT, exist_ok=True)

def probe(p):
    j = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height,r_frame_rate:format=duration", "-of", "json", p]))
    s = j["streams"][0]; n, d = s["r_frame_rate"].split("/")
    return dict(w=s["width"], h=s["height"], fps=float(n) / float(d), dur=float(j["format"]["duration"]))

def work(item):
    vid, p = item
    info = probe(p); info.update(id=vid, path=os.path.relpath(p, ROOT), name=os.path.basename(p))
    # scene cuts
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", p, "-map", "0:v:0", "-vf", "scale=320:-2,scdet=threshold=12",
                        "-f", "null", "-"], capture_output=True, text=True)
    info["cuts"] = [round(float(x), 3) for x in re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", r.stderr)]
    # sheets: every 2 s, 8x6 tiles = 96 s per sheet
    per = 48; step = 2.0
    nsheets = int(info["dur"] // (per * step)) + 1
    info["sheets"] = []
    for k in range(nsheets):
        t0 = k * per * step
        out = os.path.join(OUT, f"{vid}_s{k:02d}.jpg")
        vf = (f"fps=1/{step},scale=300:168:force_original_aspect_ratio=decrease,pad=300:168:(ow-iw)/2:(oh-ih)/2,"
              f"drawtext=fontfile={FONT}:text='%{{pts\\:hms\\:{t0}}}':x=4:y=4:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,"
              f"tile=8x6")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", str(per * step), "-i", p,
                        "-vf", vf, "-frames:v", "1", "-q:v", "4", out], check=True)
        info["sheets"].append(os.path.relpath(out, ROOT))
    return info

items = [(f"v{i+1:02d}", p) for i, p in enumerate(SRC)]
with ThreadPoolExecutor(10) as ex:
    res = list(ex.map(work, items))
json.dump(res, open(os.path.join(ROOT, "work", "sources.json"), "w"), ensure_ascii=False, indent=1)
for r in res:
    print(r["id"], f'{r["w"]}x{r["h"]}', f'{r["dur"]:.0f}s', len(r["cuts"]), "cuts", len(r["sheets"]), "sheets", r["name"])
