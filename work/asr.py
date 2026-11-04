import json, sys, whisper

src = sys.argv[1]
out = sys.argv[2]
m = whisper.load_model("small", device="cuda")
r = m.transcribe(src, language="zh", word_timestamps=True,
                 initial_prompt="陈升 刘佳慧 牡丹亭外 歌词，简体中文。",
                 condition_on_previous_text=False)
segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"],
         "words": [[round(w["start"], 2), round(w["end"], 2), w["word"]] for w in s.get("words", [])]}
        for s in r["segments"]]
json.dump(segs, open(out, "w"), ensure_ascii=False, indent=1)
for s in segs:
    print(f'{s["start"]:7.2f} {s["end"]:7.2f} {s["text"]}')
