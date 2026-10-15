"""Ditado nos chats: transcreve a fala gravada no microfone com o Whisper, no computador. Fica aberto para a resposta ser rápida.
Roda no ambiente do Whisper (whisper/, na pasta de dados do aplicativo). Uma linha JSON por pedido: entra {"id": 1, "arq": "/caminho"} e sai {"id": 1, "texto": "…"}."""
import json, os, sys
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):          # a saída é JSON em UTF-8, também no Windows
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main():
    from faster_whisper import WhisperModel
    modelo = WhisperModel(os.environ.get("ATLAS_WHISPER_FALA", "large-v3-turbo"), device="cpu", compute_type="int8", cpu_threads=8)
    print(json.dumps({"pronto": True}), flush=True)
    for linha in sys.stdin:
        try:
            p = json.loads(linha)
            segs, _ = modelo.transcribe(p["arq"], language="pt", beam_size=1, vad_filter=True, condition_on_previous_text=False, without_timestamps=True)
            r = {"texto": " ".join(s.text.strip() for s in segs).strip()}
        except Exception as e:
            r = {"erro": str(e)[:300]}
        print(json.dumps({"id": p.get("id") if isinstance(p, dict) else None, **r}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
