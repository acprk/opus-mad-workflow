import json, re, subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from paths import WK, P

S = json.load(open(f"{WK}/sources.json"))
for s in S:
    s["path"] = P(s["path"])

def det(s):
    # sample 40 points across the video
    res = Counter()
    for k in range(40):
        t = s["dur"] * (k + 0.5) / 40
        r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{t:.2f}", "-i", s["path"], "-frames:v", "8",
                            "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"],
                           capture_output=True, text=True)
        m = re.findall(r"crop=(\d+:\d+:\d+:\d+)", r.stderr)
        if m:
            res[m[-1]] += 1
    return s["id"], s["w"], s["h"], res.most_common(4)

with ThreadPoolExecutor(16) as ex:
    for sid, w, h, mc in ex.map(det, S):
        print(sid, f"{w}x{h}", mc)
