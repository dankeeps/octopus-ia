"""Transcreve um vídeo ou áudio com o Whisper (faster-whisper), no computador, sem custo.

Roda no ambiente do Whisper (Python 3.11 ou mais novo, com faster-whisper), criado pelo instalar.py:
    <dados>/whisper/bin/python whisper_transcrever.py ENTRADA SAIDA.srt

Escreve uma linha JSON por evento no stdout: {"duracao": s}, {"t": s} a cada trecho, {"fim": true, "idioma": "pt"}.
O modelo padrão é o large-v3-turbo (o mesmo da skill estudo-de-anuncio); ATLAS_WHISPER_MODELO troca.
"""
import json, os, sys
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):          # a saída é JSON em UTF-8, também no Windows
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from faster_whisper import WhisperModel


def ts(s):
    h, r = divmod(max(0.0, s), 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)) % 1000:03d}"


def main():
    entrada, saida = sys.argv[1], sys.argv[2]
    modelo = WhisperModel(os.environ.get("ATLAS_WHISPER_MODELO", "large-v3-turbo"), device="cpu", compute_type="int8")
    palavras = os.environ.get("OCTOPUS_PALAVRAS") == "1"      # aba Transcrição: guarda o tempo de cada palavra, para o texto acompanhar o vídeo
    segs, info = modelo.transcribe(entrada, vad_filter=True, beam_size=5, word_timestamps=palavras)
    por_palavra = []
    print(json.dumps({"duracao": round(info.duration, 1)}), flush=True)
    with open(saida + ".parcial", "w", encoding="utf-8") as f:
        for i, s in enumerate(segs, 1):
            f.write(f"{i}\n{ts(s.start)} --> {ts(s.end)}\n{s.text.strip()}\n\n")
            if palavras:
                por_palavra.append({"ini": round(s.start, 2), "fim": round(s.end, 2),
                                    "p": [[round(w.start, 2), round(w.end, 2), w.word.strip()] for w in (s.words or []) if w.word.strip()]})
            print(json.dumps({"t": round(s.end, 1)}), flush=True)
    os.replace(saida + ".parcial", saida)
    if palavras:
        with open(os.path.splitext(saida)[0] + ".json", "w", encoding="utf-8") as f:
            json.dump(por_palavra, f, ensure_ascii=False)
    print(json.dumps({"fim": True, "idioma": info.language}), flush=True)


if __name__ == "__main__":
    main()
