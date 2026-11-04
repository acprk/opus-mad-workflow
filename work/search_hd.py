"""Search YouTube for Chen Sheng songs; report candidates with channel, duration and max height."""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

SONGS = sys.argv[1:] or [
    "北京一夜", "把悲傷留給自己", "恨情歌", "牡丹亭外", "不再讓你孤單", "風箏", "子夜二點半", "細漢仔",
    "一個人的生活", "老嬉皮", "然後呢", "二號出口", "思念人之歌", "鼓聲若響", "責任", "關於男人",
    "浮雲車站", "歸鄉", "61號省道", "穗花", "路口", "汀州路的春天", "告訴媽媽", "布考斯基協奏曲",
    "家在北極村", "我喜歡私奔和我自己", "冬嬉皮", "擁擠的樂園", "凡人歌", "愛情的槍",
]
import os
YT = os.environ.get("YT_DLP", "yt-dlp")


def search(song):
    q = f"ytsearch8:陳昇 {song}"
    out = subprocess.run([YT, "--no-warnings", "--flat-playlist", "--print",
                          "%(id)s\t%(duration)s\t%(channel)s\t%(title)s", q], capture_output=True, text=True).stdout
    rows = [l.split("\t") for l in out.strip().splitlines() if l.count("\t") == 3]
    return song, rows


def height(vid):
    out = subprocess.run([YT, "--no-warnings", "-J", f"https://www.youtube.com/watch?v={vid}"],
                         capture_output=True, text=True).stdout
    try:
        j = json.loads(out)
        return max((f.get("height") or 0) for f in j["formats"] if f.get("vcodec") not in (None, "none"))
    except Exception:
        return -1


with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(search, SONGS))
cand = []
for song, rows in res:
    for vid, dur, ch, title in rows:
        if song.replace(" ", "") in title.replace(" ", "") or song[:2] in title:
            cand.append((song, vid, dur, ch, title))
with ThreadPoolExecutor(12) as ex:
    hs = list(ex.map(lambda c: height(c[1]), cand))
for (song, vid, dur, ch, title), h in zip(cand, hs):
    print(f"{song}\t{vid}\t{h}p\t{dur}s\t{ch}\t{title}")
