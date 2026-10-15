"""Transcreve vários vídeos ou áudios de uma vez (o modelo carrega uma vez só). Roda no ambiente do Whisper:
    <dados>/whisper/bin/python whisper_lote.py ARQ1 ARQ2 …
Uma linha JSON por arquivo no stdout: {"arq": …, "texto": …, "duracao": s} ou {"arq": …, "erro": …}."""
import json, os, sys
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):          # a saída é JSON em UTF-8, também no Windows
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from faster_whisper import WhisperModel


def main():
    modelo = WhisperModel(os.environ.get("ATLAS_WHISPER_MODELO", "large-v3-turbo"), device="cpu", compute_type="int8")
    for arq in sys.argv[1:]:
        try:
            segs, info = modelo.transcribe(arq, vad_filter=True, beam_size=5)
            texto = " ".join(s.text.strip() for s in segs).strip()
            print(json.dumps({"arq": arq, "texto": texto, "duracao": round(info.duration, 1), "idioma": info.language}, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"arq": arq, "erro": str(e)[:200]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
