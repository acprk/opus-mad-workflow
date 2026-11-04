"""Wait out YouTube's bot-check, then download the list slowly (one at a time, with pauses)."""
import glob, os, random, subprocess, sys, time

from paths import ROOT, WK

D = f"{ROOT}/extra_hd"
YT = os.environ.get("YT_DLP", "yt-dlp")
os.makedirs(D, exist_ok=True)
LIST = f"{WK}/hd_download_list.txt"
COOKIES = sys.argv[1] if len(sys.argv) > 1 else None
ids = [l.strip() for l in open(LIST) if l.strip() and not l.startswith("#")]
FMT = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]"


def done(vid):
    return any(not p.endswith(".part") for p in glob.glob(f"{D}/*[[]{vid}[]].mp4"))


def fetch(vid):
    cmd = [YT, "--no-warnings", "-f", FMT, "--merge-output-format", "mp4", "--retries", "3",
           "-o", f"{D}/%(title).70s [%(id)s].mp4", f"https://www.youtube.com/watch?v={vid}"]
    if COOKIES:
        cmd[1:1] = ["--cookies", COOKIES]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr.strip().splitlines() or [""])[-1]


log = open(f"{D}/dl_log.txt", "a")
while True:
    todo = [v for v in ids if not done(v)]
    if not todo:
        print("ALL DONE", file=log, flush=True)
        break
    ok, msg = fetch(todo[0])
    print(time.strftime("%H:%M:%S"), todo[0], "OK" if ok else "FAIL", msg[:160], file=log, flush=True)
    if not ok and ("not a bot" in msg or "reloaded" in msg or "format is not available" in msg):
        time.sleep(900)  # still blocked: wait 15 min
        continue
    if not ok:
        ids.remove(todo[0])  # other error (removed/private): skip
    time.sleep(random.uniform(20, 40))
