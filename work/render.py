"""Render the MAD from edl.json.

Stage 1 (parallel ffmpeg): each EDL clip -> clips/NNN.mp4, 1920x1080@30, cropped/graded, with handles.
Stage 2 (python): composite frames (ken-burns, transitions, lyrics, cards, grain, vignette) -> ffmpeg encoder.

usage: python3 render.py [--preview] [--from SEC --to SEC] [--only-stage1]
"""
import argparse, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 816, 30      # picture area (2.353:1)
CW, CH, PY = 1920, 1080, 132   # canvas and picture offset (letterbox)
from paths import ROOT, WK, P as resolve

SRC = {s["id"]: dict(s, path=resolve(s["path"])) for s in json.load(open(f"{WK}/sources.json"))}
BEATS = np.array(json.load(open(f"{WK}/beats.json"))["beats"])
IBI = 0.71444
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-SemiBold.ttc"
SERIF_L = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Light.ttc"
KAI = "/usr/share/fonts/truetype/arphic-gkai00mp/gkai00mp.ttf"
HANDLE = 1.0  # seconds of extra footage on each side for transitions

GRADES = {
    # memory: old MVs, warm & slightly faded
    "warm": "eq=contrast=1.05:saturation=0.82:gamma=1.0,colorbalance=rs=0.03:bs=-0.04:rm=0.02:bm=-0.02",
    # faded dream: lower saturation, lifted blacks
    "dream": "eq=contrast=0.95:saturation=0.55:brightness=0.02,colorbalance=rs=0.05:gs=0.01:bs=-0.05,curves=all='0/0.06 1/0.97'",
    "opera": "eq=contrast=1.04:saturation=0.95,colorbalance=rs=0.02:bs=-0.02",
    "live": "eq=contrast=1.06:saturation=0.9,colorbalance=rs=0.02:bs=-0.01",
    "cool": "eq=contrast=1.03:saturation=0.8,colorbalance=rs=-0.02:bs=0.03",
    "none": "null",
}


def beat_time(b):
    b = float(b)
    n = len(BEATS)
    if b <= 0:
        return BEATS[0] + b * IBI
    if b >= n - 1:
        return BEATS[-1] + (b - (n - 1)) * IBI
    i = int(b)
    return BEATS[i] + (b - i) * (BEATS[i + 1] - BEATS[i])


def load_edl():
    e = json.load(open(f"{WK}/edl.json"))
    clips = [c for c in e["clips"]]
    for i, c in enumerate(clips[:-1]):
        c["idx"] = i
        c["t0"] = c["t"] if "t" in c else beat_time(c["b"])
        nxt = clips[i + 1]
        c["t1"] = nxt["t"] if "t" in nxt else beat_time(nxt["b"])
    return e, clips[:-1]


# active picture (x, y, w, h) inside each source, from cropdetect; burned lyrics mostly live outside it
ACTIVE = {
    "v01": (0, 56, 640, 368), "v02": (0, 84, 960, 540), "v03": (0, 0, 1920, 1080), "v04": (0, 44, 640, 272),
    "v05": (32, 0, 476, 360), "v06": (0, 0, 640, 360), "v07": (0, 0, 360, 360), "v08": (0, 2, 480, 358),
    "v09": (0, 44, 640, 272), "v10": (0, 0, 640, 360), "v11": (6, 2, 530, 356), "v12": (10, 48, 460, 272),
    "v13": (0, 44, 640, 272), "v14": (2, 46, 490, 266), "v15": (10, 48, 460, 272), "v16": (0, 44, 640, 272),
    "v17": (4, 44, 472, 278), "v18": (0, 92, 1920, 896),
}
# default vertical placement of the 2.35 window inside the active area (0=top, 1=bottom)
DEFAULT_GRADE = {"v14": "opera", "v07": "dream", "v11": "dream", "v17": "dream", "v08": "dream",
                 "v03": "live", "v05": "live", "v06": "live", "v10": "live", "v01": "none"}
DEFAULT_CY = {"v01": 0.3, "v03": 0.3, "v05": 0.35, "v08": 0.3, "v11": 0.3, "v12": 0.4, "v15": 0.4}


def crop_box(c):
    if c.get("crop"):
        return c["crop"]
    ax, ay, aw, ah = ACTIVE[c["src"]]
    asp = W / H
    if aw / ah > asp:
        h = ah; w = round(ah * asp)
    else:
        w = aw; h = round(aw / asp)
    zc = c.get("zc", 1.0)  # extra static zoom-crop (>1 = tighter)
    w = round(w / zc); h = round(h / zc)
    cx = c.get("cx", 0.5); cy = c.get("cy", DEFAULT_CY.get(c["src"], 0.5))
    x = ax + round((aw - w) * cx); y = ay + round((ah - h) * cy)
    return [x - x % 2, y - y % 2, w - w % 2, h - h % 2]


def crop_filter(c):
    x, y, w, h = crop_box(c)
    return f"crop={int(w)}:{int(h)}:{int(x)}:{int(y)}"


def stage1_one(c):
    out = f"{WK}/clips/{c['idx']:03d}.mp4"
    spd = c.get("speed", 1.0)
    dur = (c["t1"] - c["t0"]) + 2 * HANDLE  # timeline seconds needed
    src_in = c["in"] - HANDLE * spd
    pre_pad = 0.0
    if src_in < 0:
        pre_pad = -src_in / spd; src_in = 0.0
    s = SRC[c["src"]]
    vf = [crop_filter(c), f"scale={W}:{H}:flags=lanczos", "setsar=1"]
    if s["h"] < 700:
        vf.append("unsharp=5:5:0.5:5:5:0.0")
    vf.append(GRADES[c.get("grade", DEFAULT_GRADE.get(c["src"], "warm"))])
    if c.get("hflip"):
        vf.append("hflip")
    vf.append(f"setpts=(PTS-STARTPTS)/{spd}")
    vf.append(f"fps={FPS}")
    if pre_pad > 0:
        vf.append(f"tpad=start_duration={pre_pad:.3f}:start_mode=clone")
    vf.append(f"tpad=stop_duration={dur:.3f}:stop_mode=clone")
    nfr = int(round(dur * FPS)) + 2
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{src_in:.3f}", "-t", f"{dur * spd + 1:.3f}", "-i", s["path"],
           "-an", "-vf", ",".join(vf), "-frames:v", str(nfr), "-c:v", "libx264", "-preset", "fast", "-crf", "12",
           "-pix_fmt", "yuv420p", "-threads", "2", out]
    key = json.dumps([cmd, c.get("in")], ensure_ascii=False)
    stamp = out + ".key"
    if os.path.exists(out) and os.path.exists(stamp) and open(stamp).read() == key:
        return
    subprocess.run(cmd, check=True)
    open(stamp, "w").write(key)


class ClipReader:
    def __init__(self, c):
        self.c = c
        self.cap = cv2.VideoCapture(f"{WK}/clips/{c['idx']:03d}.mp4")
        self.pos = 0; self.last = None

    def frame_at(self, t):
        """timeline time t -> frame (BGR) of this clip."""
        k = int(round((t - self.c["t0"] + HANDLE) * FPS))
        k = max(k, 0)
        if k < self.pos - 1:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, k); self.pos = k; self.last = None
        while self.pos <= k:
            ok, f = self.cap.read()
            if ok:
                self.last = f
            self.pos += 1
        return self.last

    def close(self):
        self.cap.release()


def kenburns(img, c, t):
    z = c.get("zoom", [1.0, 1.05])
    p = (t - c["t0"]) / max(1e-3, c["t1"] - c["t0"])
    p = min(max(p, -0.3), 1.3)
    s = z[0] + (z[1] - z[0]) * p
    ax, ay = c.get("anchor", [0.5, 0.5])
    if abs(s - 1.0) < 1e-4:
        return img
    M = np.array([[s, 0, (1 - s) * ax * W], [0, s, (1 - s) * ay * H]], dtype=np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


# ---------- text rendering ----------

def shadowed(layer_draw_fn, blur=6, shadow_alpha=170):
    txt = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    layer_draw_fn(ImageDraw.Draw(txt), (255, 255, 255, 255))
    sh = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    layer_draw_fn(ImageDraw.Draw(sh), (0, 0, 0, shadow_alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(sh, txt)


def spaced_text(d, xy, text, font, fill, spacing, anchor_center=True):
    widths = [font.getlength(ch) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x, y = xy
    if anchor_center:
        x -= total / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill)
        x += w + spacing


def lyric_layer(text, kind):
    if kind == "opera":
        # vertical kaishu at the right edge of the picture, like a hanging scroll
        f = ImageFont.truetype(KAI, 58)
        n = len(text.replace(" ", "")) + 0.4 * text.count(" ")
        def draw(d, fill):
            x = CW - 190; y = PY + (H - n * 68) / 2
            for ch in text:
                if ch == " ":
                    y += 27; continue
                d.text((x, y), ch, font=f, fill=fill); y += 68
        return shadowed(draw, blur=7, shadow_alpha=210)
    f = ImageFont.truetype(SERIF_L, 44)
    def draw(d, fill):
        spaced_text(d, (CW / 2, PY + H + 38), text, f, fill, spacing=12)
    return shadowed(draw, blur=4, shadow_alpha=120)


def card_layer(spec):
    def draw(d, fill):
        for item in spec["items"]:
            font = ImageFont.truetype({"kai": KAI, "serif": SERIF, "light": SERIF_L}[item.get("font", "serif")], item["size"])
            col = tuple(item.get("color", fill[:3])) + (fill[3],) if fill[:3] == (255, 255, 255) else fill
            if item.get("vertical"):
                x, y = item["xy"]
                for ch in item["text"]:
                    d.text((x, y), ch, font=font, fill=col); y += item["size"] * 1.18
            else:
                spaced_text(d, item["xy"], item["text"], font, col, item.get("spacing", 6), item.get("center", True))
    return shadowed(draw, blur=8, shadow_alpha=150)


def to_premult(layer):
    """-> (premultiplied BGR*255, alpha, bbox) cropped to the layer's visible box."""
    x0, y0, x1, y1 = layer.getbbox() or (0, 0, 1, 1)
    a = np.asarray(layer.crop((x0, y0, x1, y1))).astype(np.float32) / 255.0
    rgb = a[..., :3][..., ::-1]  # to BGR
    al = a[..., 3:4]
    return rgb * al * 255.0, al, (x0, y0, x1, y1)


def over(base, layer, alpha):
    rgbp, al, (x0, y0, x1, y1) = layer
    roi = base[y0:y1, x0:x1]
    base[y0:y1, x0:x1] = roi * (1 - al * alpha) + rgbp * alpha
    return base


def env(t, t0, t1, fin=0.35, fout=0.45):
    if t < t0 or t > t1:
        return 0.0
    return min(1.0, (t - t0) / fin, (t1 - t) / fout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--from", dest="tfrom", type=float, default=0.0)
    ap.add_argument("--to", dest="tto", type=float, default=None)
    ap.add_argument("--only-stage1", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--noaudio", action="store_true")
    ap.add_argument("--skip-stage1", action="store_true")
    a = ap.parse_args()

    edl, clips = load_edl()
    os.makedirs(f"{WK}/clips", exist_ok=True)
    T_END = edl["end"]
    tto = a.tto if a.tto is not None else T_END
    need = [c for c in clips if c["t1"] + HANDLE >= a.tfrom and c["t0"] - HANDLE <= tto]
    if not a.skip_stage1:
        with ThreadPoolExecutor(14) as ex:
            list(ex.map(stage1_one, need))
    print(f"stage1 done: {len(need)} clips", file=sys.stderr)
    if a.only_stage1:
        return

    # lyrics: snap to nearest beat, end at next line start
    lyr = json.load(open(f"{WK}/lyrics.json"))
    LY = []
    for i, (t, txt, kind) in enumerate(lyr):
        bar = lambda x: BEATS[4 * int(round(np.argmin(abs(BEATS - x)) / 4))]  # lines start on bar lines
        ts = bar(t) - 0.12
        nxt = lyr[i + 1][0] if i + 1 < len(lyr) else t + 6
        te = min(ts + 5.6, bar(nxt) - 0.25)
        LY.append((ts, te, to_premult(lyric_layer(txt, kind)), kind))
    CARDS = [(c["t0"], c["t1"], to_premult(card_layer(c)), c.get("fin", 0.8), c.get("fout", 0.8)) for c in edl.get("cards", [])]

    # grain + vignette
    rng = np.random.default_rng(7)
    grains = [cv2.resize(rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32), (W, H))[..., None] for _ in range(6)]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    vign = (1 - 0.32 * np.clip(r - 0.45, 0, None) ** 1.6)[..., None].astype(np.float32)

    out = a.out or (f"{WK}/preview.mp4" if a.preview else f"{ROOT}/output/chensheng_mudanting_mad.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ow, oh = (960, 540) if a.preview else (CW, CH)
    venc = ["-c:v", "libx264", "-preset", "veryfast" if a.preview else "slow", "-crf", "23" if a.preview else "16",
            "-pix_fmt", "yuv420p", "-threads", "4"]
    if a.noaudio:
        enc = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ow}x{oh}", "-r", str(FPS),
               "-i", "-", *venc, out]
    else:
        enc = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ow}x{oh}", "-r", str(FPS), "-i", "-",
               "-ss", f"{a.tfrom:.3f}", "-t", f"{tto - a.tfrom:.3f}", "-i", resolve(edl["audio"]),
               "-map", "0:v", "-map", "1:a", *venc, "-c:a", "aac", "-b:a", "320k",
               "-movflags", "+faststart", "-shortest", out]
    P = subprocess.Popen(enc, stdin=subprocess.PIPE)

    readers = {}
    n0 = int(round(a.tfrom * FPS)); n1 = int(round(tto * FPS))
    flashes = edl.get("flashes", [])
    for n in range(n0, n1):
        t = n / FPS
        # active clips: current + neighbour during transition
        cur = None
        for c in clips:
            if c["t0"] <= t < c["t1"]:
                cur = c; break
        if cur is None:
            frame = np.zeros((H, W, 3), np.float32)
        else:
            def get(c):
                if c["idx"] not in readers:
                    readers[c["idx"]] = ClipReader(c)
                f = readers[c["idx"]].frame_at(t)
                if f is None:
                    return np.zeros((H, W, 3), np.float32)
                return kenburns(f, c, t).astype(np.float32)
            frame = get(cur)
            # incoming transition of cur
            tr = cur.get("tr", "cut"); L = cur.get("tl", 0.5) * IBI
            i = cur["idx"]
            nxt = clips[i + 1] if i + 1 < len(clips) else None
            prv = clips[i - 1] if i > 0 else None
            if tr == "fade" and prv is not None and t < cur["t0"] + L / 2:
                w = 0.5 + (t - cur["t0"]) / L
                frame = frame * w + get(prv) * (1 - w)
            if nxt is not None and nxt.get("tr") == "fade":
                Ln = nxt.get("tl", 0.5) * IBI
                if t >= nxt["t0"] - Ln / 2:
                    w = 0.5 - (nxt["t0"] - t) / Ln
                    frame = frame * (1 - w) + get(nxt) * w
            if tr in ("black", "white") and t < cur["t0"] + L:
                k = 1 - (t - cur["t0"]) / L
                col = 255.0 if tr == "white" else 0.0
                frame = frame * (1 - k) + col * k
            if nxt is not None and nxt.get("tr") in ("black", "white"):
                Ln = nxt.get("tl", 0.5) * IBI
                if t >= nxt["t0"] - Ln:
                    k = 1 - (nxt["t0"] - t) / Ln
                    col = 255.0 if nxt["tr"] == "white" else 0.0
                    frame = frame * (1 - k) + col * k
            if tr == "flash" and t < cur["t0"] + 0.30:
                k = 0.85 * (1 - (t - cur["t0"]) / 0.30) ** 1.5
                frame = frame * (1 - k) + 255.0 * k
        for ft in flashes:
            if ft <= t < ft + 0.25:
                k = 0.6 * (1 - (t - ft) / 0.25) ** 1.5
                frame = frame * (1 - k) + 255.0 * k
        # global fades
        if t < edl.get("fade_in", 0):
            frame *= t / edl["fade_in"]
        fo = edl.get("fade_out")
        if fo and t > T_END - fo:
            frame *= max(0.0, (T_END - t) / fo)
        frame = frame * vign
        frame += grains[n % len(grains)] * 5.0
        canvas = np.zeros((CH, CW, 3), np.float32)
        canvas[PY:PY + H] = frame
        frame = canvas
        for (c0, c1, lay, fi, fo2) in CARDS:
            al = env(t, c0, c1, fi, fo2)
            if al > 0:
                frame = over(frame, lay, al)
        for (ts, te, lay, kind) in LY:
            al = env(t, ts, te)
            if al > 0:
                frame = over(frame, lay, al)
        img = np.clip(frame, 0, 255).astype(np.uint8)
        if a.preview:
            img = cv2.resize(img, (ow, oh), interpolation=cv2.INTER_AREA)
        P.stdin.write(img.tobytes())
        # free finished readers
        for k in [k for k in readers if clips[k]["t1"] + 2 < t]:
            readers.pop(k).close()
        if n % 300 == 0:
            print(f"  t={t:6.1f}s", file=sys.stderr)
    P.stdin.close(); P.wait()
    print("wrote", out, file=sys.stderr)


if __name__ == "__main__":
    main()
