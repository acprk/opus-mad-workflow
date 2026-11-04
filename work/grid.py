"""Fit a steady beat grid to librosa beats and report bar lines near lyric starts."""
import json, numpy as np

from paths import WK

B = np.array(json.load(open(f"{WK}/beats.json"))["beats"])
L = json.load(open(f"{WK}/lyrics.json"))
i = np.arange(len(B))
k, b = np.polyfit(i, B, 1)
res = B - (k * i + b)
print(f"ibi {k:.5f}s  bpm {60/k:.3f}  offset {b:.3f}  resid sd {res.std():.3f} max {abs(res).max():.3f}")
# piecewise drift check
for lo in range(0, len(B), 60):
    seg = slice(lo, lo + 60)
    print(f"  beats {lo:3d}-{lo+59:3d}  mean resid {res[seg].mean():+.3f}")
# phase of lyric starts in beats
for t, txt, _ in L:
    j = np.argmin(abs(B - t))
    print(f"{t:7.2f} nearest beat #{j:3d} at {B[j]:7.2f} (d={t-B[j]:+.2f}) beat%4={j%4} {txt}")
