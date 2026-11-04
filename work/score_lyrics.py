"""Score candidate lyric texts against an audio window with whisper teacher forcing."""
import torch, whisper
from whisper.tokenizer import get_tokenizer

AUDIO = "bgm_full.wav"
# (start, end, [candidates])
TESTS = [
    (76.5, 82.5, ["马不能越千里", "怕不能越千里", "怕不能遇见你"]),
    (212.5, 225.5, ["你问我怕什么 怕不能越千里", "你问我怕什么 怕不能遇见你", "你问我怕什么 马不能越千里"]),
    (162.0, 168.6, ["你把谁放那", "你把心放哪", "你抱过新娘啊"]),
    (230.8, 236.2, ["惶惶忽忽一瞬间", "恍恍惚惚一瞬间", "晃晃忽忽一瞬间"]),
    (187.5, 196.8, ["可我最爱是天然", "可我追爱是天然"]),
    (70.8, 76.5, ["这人间苦什么", "这人间怕什么"]),
]

model = whisper.load_model("small", device="cuda")
tok = get_tokenizer(model.is_multilingual, language="zh", task="transcribe")
audio = whisper.load_audio(AUDIO)
for s, e, cands in TESTS:
    seg = whisper.pad_or_trim(audio[int(s * 16000):int(e * 16000)])
    mel = whisper.log_mel_spectrogram(seg).to(model.device)
    with torch.no_grad():
        feats = model.embed_audio(mel[None])
    print(f"--- {s}-{e}")
    for c in cands:
        prefix = list(tok.sot_sequence_including_notimestamps)
        body = tok.encode(c) + [tok.eot]
        toks = torch.tensor([prefix + body], device=model.device)
        with torch.no_grad():
            logits = model.logits(toks[:, :-1], feats)
        lp = torch.log_softmax(logits.float(), -1)
        n0 = len(prefix) - 1
        tgt = toks[0, n0 + 1:]
        ll = lp[0, n0:, :].gather(-1, tgt[:, None]).squeeze(-1)
        print(f"  {ll.sum().item():8.2f}  per-tok {ll.mean().item():6.2f}  {c}")
