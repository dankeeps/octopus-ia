#!/usr/bin/env python3
"""Mede tempo e caracteres de cada bloco de uma VSL.

Uso:
  python3 medir_blocos.py TRANSCRICAO BLOCOS.json [--duracao 42:10] [--json]

TRANSCRICAO: .srt, .vtt, .json do Whisper (com "segments") ou texto puro (.txt/.md).
BLOCOS.json: lista na ordem da VSL, cada item com o nome do bloco e as primeiras
palavras exatas dele na transcrição:
  [{"bloco": "Lead", "inicio": "Se você já tentou de tudo"},
   {"bloco": "Background", "inicio": "Prazer, meu nome é"}, ...]

Com marcação de tempo (srt, vtt, Whisper), a duração vem da transcrição.
Sem marcação, é estimada: pela --duracao total da VSL, se informada, ou por
14,5 caracteres por segundo (fala em português num ritmo de VSL).
"""
import json, re, sys, unicodedata, argparse

CPS_PADRAO = 14.5


def ts(s):
    s = s.strip().replace(",", ".")
    p = [float(x) for x in s.split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def ler_transcricao(caminho):
    """Devolve lista de segmentos (inicio, fim, texto); inicio/fim None se não houver tempo."""
    bruto = open(caminho, encoding="utf-8-sig").read()
    low = caminho.lower()
    if low.endswith(".json"):
        d = json.loads(bruto)
        segs = d.get("segments", d) if isinstance(d, dict) else d
        return [(float(s["start"]), float(s["end"]), s["text"].strip()) for s in segs]
    if low.endswith((".srt", ".vtt")):
        segs = []
        for bloco in re.split(r"\n\s*\n", bruto.replace("\r", "")):
            m = re.search(r"([\d:.,]+)\s*-->\s*([\d:.,]+)", bloco)
            if not m:
                continue
            linhas = bloco[m.end():].strip().splitlines()
            texto = " ".join(l.strip() for l in linhas if l.strip())
            texto = re.sub(r"<[^>]+>", "", texto)
            if texto:
                segs.append((ts(m.group(1)), ts(m.group(2)), texto))
        return segs
    return [(None, None, re.sub(r"\s+", " ", bruto).strip())]


def normalizar(texto):
    """Texto sem acento, minúsculo, só letras e números; guarda o índice original de cada caractere."""
    out, idx = [], []
    espaco = True
    for i, c in enumerate(texto):
        b = unicodedata.normalize("NFD", c.lower())
        b = "".join(x for x in b if unicodedata.category(x) != "Mn")
        if b and b.isalnum():
            out.append(b[0]); idx.append(i); espaco = False
        elif not espaco:
            out.append(" "); idx.append(i); espaco = True
    return "".join(out), idx


def mmss(seg):
    seg = int(round(seg))
    return f"{seg // 60:02d}:{seg % 60:02d}"


def medir(segs, blocos, duracao_total=None):
    texto, offsets, pos = "", [], 0
    for ini, fim, t in segs:
        if texto:
            texto += " "; pos += 1
        offsets.append((pos, pos + len(t), ini, fim))
        texto += t; pos += len(t)
    norm, mapa = normalizar(texto)

    inicios, busca = [], 0
    for b in blocos:
        alvo, _ = normalizar(b["inicio"])
        alvo = alvo.strip()
        achou = norm.find(alvo, busca)
        if achou < 0:
            raise SystemExit(f'Não achei o início do bloco "{b["bloco"]}": "{b["inicio"]}". '
                             "Copie as primeiras palavras exatamente como estão na transcrição.")
        inicios.append(mapa[achou]); busca = achou + len(alvo)
    inicios.append(len(texto))

    com_tempo = segs and segs[0][0] is not None

    def tempo_em(o):
        for a, z, ini, fim in offsets:
            if o <= z:
                if o <= a:
                    return ini
                return ini + (fim - ini) * (o - a) / max(1, z - a)
        return offsets[-1][3]

    total_chars = len(texto[inicios[0]:].strip())
    if com_tempo:
        fonte = "marcação de tempo da transcrição"
        fim_total = offsets[-1][3]
    else:
        cps = len(texto) - inicios[0]
        cps = cps / duracao_total if duracao_total else CPS_PADRAO
        fonte = (f"estimado pela duração total ({mmss(duracao_total)}): {cps:.1f} caracteres por segundo"
                 if duracao_total else f"estimado por {CPS_PADRAO} caracteres por segundo (sem duração total)")

    linhas = []
    for i, b in enumerate(blocos):
        trecho = texto[inicios[i]:inicios[i + 1]].strip()
        chars = len(trecho)
        if com_tempo:
            t0 = tempo_em(inicios[i])
            t1 = tempo_em(inicios[i + 1]) if i + 1 < len(blocos) else fim_total
        else:
            t0 = (inicios[i] - inicios[0]) / cps
            t1 = (inicios[i + 1] - inicios[0]) / cps
        linhas.append({"bloco": b["bloco"], "inicio": mmss(t0), "inicio_s": round(t0, 1),
                       "duracao": mmss(t1 - t0), "duracao_s": round(t1 - t0, 1), "caracteres": chars})
    total_s = sum(l["duracao_s"] for l in linhas) or 1
    for l in linhas:
        l["pct"] = round(100 * l["duracao_s"] / total_s)
    return {"fonte_tempo": fonte, "duracao_total": mmss(total_s), "caracteres_total": total_chars, "blocos": linhas}


def tabela(r):
    out = ["| Bloco | Início | Duração | Caracteres | % da VSL |", "|---|---|---|---|---|"]
    for l in r["blocos"]:
        out.append(f'| {l["bloco"]} | {l["inicio"]} | {l["duracao"]} | {l["caracteres"]:,} | {l["pct"]}% |'.replace(",", "."))
    out.append(f'| **Total** |  | {r["duracao_total"]} | {r["caracteres_total"]:,} | 100% |'.replace(",", "."))
    out.append("")
    out.append(f'Tempo medido por: {r["fonte_tempo"]}.')
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcricao")
    ap.add_argument("blocos")
    ap.add_argument("--duracao", help="duração total da VSL (mm:ss ou hh:mm:ss), para transcrição sem tempo")
    ap.add_argument("--json", action="store_true", help="saída em JSON em vez de tabela")
    a = ap.parse_args()
    r = medir(ler_transcricao(a.transcricao), json.load(open(a.blocos, encoding="utf-8")),
              ts(a.duracao) if a.duracao else None)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else tabela(r))
