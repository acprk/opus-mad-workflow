import json, numpy as np, librosa

from paths import WK

y, sr = librosa.load(f"{WK}/bgm_full.wav", sr=22050, mono=True)
tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
onset = librosa.onset.onset_detect(y=y, sr=sr, units="time", backtrack=False)
rms = librosa.feature.rms(y=y, hop_length=2205)[0]  # 0.1 s hops
db = 20 * np.log10(rms + 1e-6)
print("tempo", tempo, "nbeats", len(beats), "dur", len(y) / sr)
print("first beats", np.round(beats[:24], 2))
ib = np.diff(beats); print("median IBI", np.median(ib))
# energy per 4 s
for t in range(0, int(len(y) / sr), 4):
    seg = db[t * 10:(t + 4) * 10]
    print(f"{t:4d}s {seg.mean():6.1f} dB " + "#" * int(max(0, seg.mean() + 40)))
json.dump({"tempo": float(np.atleast_1d(tempo)[0]), "beats": [round(float(b), 3) for b in beats],
           "onsets": [round(float(o), 3) for o in onset],
           "rms_db_100ms": [round(float(v), 1) for v in db]},
          open(f"{WK}/beats.json", "w"))
