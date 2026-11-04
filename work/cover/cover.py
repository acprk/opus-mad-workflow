"""B站封面 1920x1080：白发陈升（现在）+ 半透明的青年陈升（梦）+ 竖排楷书标题。"""
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

import os

D = os.path.dirname(os.path.abspath(__file__))  # put the extracted frames (v03_290.png, v17_106.5.png) here
KAI = "/usr/share/fonts/truetype/arphic-gkai00mp/gkai00mp.ttf"
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Light.ttc"
SERIF_B = "/usr/share/fonts/opentype/noto/NotoSerifCJK-SemiBold.ttc"
W, H = 1920, 1080

# present: white-haired Chen, arm outstretched (crop away burned subtitle at bottom)
now = Image.open(f"{D}/v03_290.png").convert("RGB")
now = now.crop((0, 0, 1620, 912)).resize((W, round(912 * W / 1620)), Image.LANCZOS)
now = now.crop((0, 0, W, H))
now = ImageEnhance.Color(now).enhance(0.75)
now = ImageEnhance.Contrast(now).enhance(1.08)
arr = np.asarray(now).astype(np.float32)
arr = arr * np.array([1.04, 1.0, 0.92])  # warm
# darken the right side for the title / ghost
xx = np.linspace(0, 1, W)[None, :, None]
arr *= 0.22 + 0.78 * np.clip((0.95 - xx) / 0.45, 0, 1) ** 0.9

# dream: young Chen in the snow (v17), faded and soft, on the left
young = Image.open(f"{D}/v17_106.5.png").convert("L")
young = young.crop((60, 40, 420, 290))  # face + scarf, above burned subtitle
young = young.resize((round(young.width * 1080 / young.height * 0.95), round(1080 * 0.95)), Image.LANCZOS)
young = young.filter(ImageFilter.GaussianBlur(1.2))
ya = np.asarray(ImageOps.autocontrast(young)).astype(np.float32)[..., None]
yw = ya.shape[1]
mask = np.zeros((ya.shape[0], yw, 1), np.float32)
yy_, xx_ = np.mgrid[0:ya.shape[0], 0:yw]
r = np.sqrt(((xx_ - yw * 0.5) / (yw * 0.5)) ** 2 + ((yy_ - ya.shape[0] * 0.45) / (ya.shape[0] * 0.55)) ** 2)
mask[..., 0] = np.clip(1.2 - r, 0, 1) ** 1.5
x0, y0 = W - yw - 40, 40
tint = np.array([1.0, 0.96, 0.86])
seg = arr[y0:y0 + ya.shape[0], x0:x0 + yw]
ghost = ya * tint
alpha = 0.42 * mask[: seg.shape[0], : seg.shape[1]]
arr[y0:y0 + ya.shape[0], x0:x0 + yw] = seg * (1 - alpha) + np.maximum(seg, ghost[: seg.shape[0], : seg.shape[1]]) * alpha

# vignette + letterbox
yy, xx2 = np.mgrid[0:H, 0:W].astype(np.float32)
rv = np.sqrt(((xx2 - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
arr *= (1 - 0.35 * np.clip(rv - 0.5, 0, None) ** 1.5)[..., None]
img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
bar = 70
d = ImageDraw.Draw(img)
d.rectangle((0, 0, W, bar), fill=(0, 0, 0)); d.rectangle((0, H - bar, W, H), fill=(0, 0, 0))

# title: vertical kaishu with soft shadow
txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
def vertical(dr, x, y, s, font, fill, step):
    for ch in s:
        dr.text((x, y), ch, font=font, fill=fill); y += step
def draw_all(dr, fill, red):
    vertical(dr, 1600, 170, "牡丹亭外", ImageFont.truetype(KAI, 168), fill, 186)
    vertical(dr, 1500, 205, "黄粱一梦二十年", ImageFont.truetype(SERIF, 46), fill, 60)
    # seal
    dr.rectangle((1625, 935, 1745, 1000), fill=red)
sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); draw_all(ImageDraw.Draw(sh), (0, 0, 0, 200), (0, 0, 0, 0))
sh = sh.filter(ImageFilter.GaussianBlur(10))
draw_all(ImageDraw.Draw(txt), (246, 240, 228, 255), (178, 34, 34, 235))
dt = ImageDraw.Draw(txt)
dt.text((1638, 938), "陈升", font=ImageFont.truetype(KAI, 52), fill=(246, 236, 220, 255))
img = Image.alpha_composite(img.convert("RGBA"), sh)
img = Image.alpha_composite(img, txt)
# small tag in the bottom bar
d2 = ImageDraw.Draw(img)
d2.text((60, H - 56), "陈升 · 全歌向 MAD", font=ImageFont.truetype(SERIF, 30), fill=(200, 196, 188, 255))
img.convert("RGB").save(f"{D}/cover.jpg", quality=93)
img.convert("RGB").resize((960, 540), Image.LANCZOS).save(f"{D}/cover_small.jpg", quality=90)
print("ok")
