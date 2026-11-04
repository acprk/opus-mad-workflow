"""Full-quality render: stage1 once, composite N time-chunks in parallel, lossless concat, mux audio."""
import json, os, subprocess, sys

from paths import ROOT, WK, P

OUT = f"{ROOT}/output/陈升_牡丹亭外_MAD_1080p.mp4"
PY = sys.executable
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6
FPS = 30
edl = json.load(open(f"{WK}/edl.json"))
nfr = int(round(edl["end"] * FPS))

subprocess.run([PY, f"{WK}/render.py", "--only-stage1"], check=True)
os.makedirs(f"{WK}/chunks", exist_ok=True)
procs, parts = [], []
for k in range(N):
    a, b = nfr * k // N, nfr * (k + 1) // N
    part = f"{WK}/chunks/part{k:02d}.mp4"
    parts.append(part)
    procs.append(subprocess.Popen([PY, f"{WK}/render.py", "--skip-stage1", "--noaudio",
                                   "--from", f"{a / FPS:.6f}", "--to", f"{b / FPS:.6f}", "--out", part],
                                  stderr=open(f"{WK}/chunks/part{k:02d}.log", "w")))
for p in procs:
    assert p.wait() == 0
with open(f"{WK}/chunks/list.txt", "w") as f:
    for p in parts:
        f.write(f"file '{p}'\n")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{WK}/chunks/list.txt",
                "-i", P(edl["audio"]), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                "-t", f"{edl['end']:.3f}", "-movflags", "+faststart", OUT], check=True)
print("wrote", OUT)
