import re, html, sys
for p in sys.argv[1:]:
    t = open(p, encoding="utf-8", errors="ignore").read()
    t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", "", t)
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = "\n".join(l.strip() for l in t.splitlines() if l.strip())
    print("=====", p)
    print(t[:4000])
