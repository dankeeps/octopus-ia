"""Controle de mercado: o estudo dos anúncios de uma oferta (os próprios e os de concorrente).

Mora dentro da oferta, no cofre:

    Projetos/{Expert}/{Oferta}/Controle de mercado/Controle de mercado.md      painel (reescrito a cada alimentação)
    Projetos/{Expert}/{Oferta}/Controle de mercado/Anúncios/CM 07 - <título>.md  uma nota por anúncio

O agente de Criativos entrega um documento (tipo: controle-de-mercado) com a transcrição e a
classificação de cada anúncio; `gravar` separa em notas. Tudo o que a sub-aba Auditoria mostra é
contado aqui, a partir dessas notas (`dados`), sem IA:

    arg     frases e parágrafos idênticos em 2+ anúncios
    ident   os trechos exatos de cada elemento persuasivo que se repetem em 2+ anúncios
    geral   a ideia (dor, desejo, promessa, prova, mecanismo, solução comum), dita de qualquer jeito
    narr    qual narrativa cada anúncio usa
"""
import datetime, re, unicodedata

import agentes
from criativos import _campo, _itens, _secao
from spy import fm_texto, ler_fm, limpar, link_obsidian

PASTA = "Controle de mercado"
SWIPE = "Swipe/Auditoria"            # onde moram os anúncios de concorrente: é do Spy, vale para todos os projetos
ATALHO = "auditoria_atalho"
MODELO = "Biblioteca/Modelos/Anúncio do controle de mercado.md"
# (nome na tela, propriedade na nota, rótulo de um item)
CATS = [("Dores", "dores", "Dor"), ("Desejos", "desejos", "Desejo"), ("Promessas", "promessas", "Promessa"),
        ("Provas", "provas", "Prova"), ("Mecanismo", "mecanismo", "Mecanismo"), ("Soluções comuns", "solucoes_comuns", "Solução comum")]
MODELO_PADRAO = """---
tipo: controle_anuncio
n:
expert: ""
oferta: ""
origem: ""
anunciante: ""
copias: 1
status: ""
duracao:
narrativa: ""
narrativa_secundaria: ""
formato: ""
dores: []
desejos: []
promessas: []
provas: []
mecanismo: []
solucoes_comuns: []
data: "{{date}}"
---
# {{title}}

## Por que esta narrativa

## Elementos persuasivos

## Transcrição
"""


class ErroControle(Exception):
    pass


def _plano(t):
    t = "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").lower()
    return t


NUMEROS = {"zero": "0", "um": "1", "uma": "1", "dois": "2", "duas": "2", "tres": "3", "quatro": "4", "cinco": "5",
           "seis": "6", "sete": "7", "oito": "8", "nove": "9", "dez": "10", "doze": "12", "quinze": "15", "vinte": "20", "trinta": "30",
           "quarenta": "40", "cinquenta": "50", "sessenta": "60", "setenta": "70", "oitenta": "80", "noventa": "90", "cem": "100"}


def _palavras(t):
    """Palavras comparáveis: sem acento, caixa nem pontuação; "pra" = "para", "três" = "3"."""
    out = []
    for w in re.findall(r"[a-z0-9%]+", _plano(t)):
        w = {"pra": "para", "pro": "para", "ta": "esta", "tava": "estava", "to": "estou"}.get(w, w)
        out.append(NUMEROS.get(w, w))
    return out


def _chave(t):
    return " ".join(_palavras(t))


def _frases(texto):
    out = []
    for m in re.finditer(r"[^.?!…]*(?:[.?!…]+|$)", texto):
        f = m.group().strip()
        if not f:
            continue
        if out and re.search(r"\b(Dr|Dra|Sr|Sra)\.$", out[-1]):
            out[-1] += " " + f
        else:
            out.append(f)
    return out


def _categoria(rotulo):
    r = _chave(rotulo)
    for nome, prop, um in CATS:
        if r in (_chave(nome), _chave(um), prop.replace("_", " ")) or r.rstrip("s") == _chave(um):
            return nome
    return None


def pasta(v, expert, oferta):
    return v / "Projetos" / expert / oferta / PASTA


# ---------------- ler as notas ----------------
def _elementos(corpo):
    """Linhas "- **Dor** · ideia — “trecho”" da seção Elementos persuasivos."""
    out = []
    for l in _secao_h2(corpo, "Elementos persuasivos").splitlines():
        m = re.match(r"^\s*-\s*\*\*(.+?)\*\*\s*·\s*(.+?)(?:\s+—\s+[“\"](.+)[”\"])?\s*$", l)
        if m and _categoria(m.group(1)):
            out.append({"cat": _categoria(m.group(1)), "ideia": m.group(2).strip(), "trecho": (m.group(3) or "").strip()})
    return out


def _secao_h2(corpo, nome):
    m = re.search(rf"^## {re.escape(nome)}[ \t]*\n(.*?)(?=^## |\Z)", corpo, re.S | re.M)
    return m.group(1).strip() if m else ""


def _sem_link(t):
    return re.sub(r"^\[\[([^\]|]+)(?:\|[^\]]*)?\]\]$", r"\1", str(t or "").strip())


def anuncios(v, expert, oferta):
    base = pasta(v, expert, oferta) / "Anúncios"
    out = []
    if not base.is_dir():
        return out
    for p in sorted(base.glob("*.md")):
        props, corpo = ler_fm(p.read_text(encoding="utf-8"))
        meu = props                                   # o que é desta oferta: número, cópias e validado
        if str(props.get("tipo") or "") == ATALHO:    # anúncio de concorrente: o arquivo mora no Spy e a oferta guarda só o atalho
            alvo = v / str(props.get("alvo") or "")
            if not alvo.is_file() or v.resolve() not in alvo.resolve().parents:
                continue
            p2, corpo = ler_fm(alvo.read_text(encoding="utf-8"))
            props = {**p2, "n": meu.get("n"), "copias": meu.get("copias"), "status": meu.get("status")}
        if str(props.get("tipo") or "") != "controle_anuncio":
            continue
        try:
            n = int(props.get("n"))
        except (TypeError, ValueError):
            continue
        num = lambda k, pad=None: int(props[k]) if str(props.get(k) or "").isdigit() else pad
        out.append({"n": n, "arq": p, "titulo": re.sub(r"^CM \d+ - ", "", p.stem), "texto": _secao_h2(corpo, "Transcrição"),
                    "origem": str(props.get("origem") or ""), "anunciante": str(props.get("anunciante") or ""),
                    "validado": _chave(props.get("status") or "").startswith("validad"),
                    "copias": num("copias", 1) or 1, "dur": num("duracao"), "formato": str(props.get("formato") or ""),
                    "narrativa": _sem_link(props.get("narrativa")), "secundaria": _sem_link(props.get("narrativa_secundaria")),
                    "porque": _secao_h2(corpo, "Por que esta narrativa"), "elementos": _elementos(corpo)})
    return sorted(out, key=lambda a: a["n"])


# ---------------- contar ----------------
def _argumentos(ads):
    """Frases iguais em 2+ anúncios; frases que andam sempre juntas viram um parágrafo."""
    seq, onde = {}, {}                       # anúncio -> [(chave, frase)]; chave -> {anúncio: posição}
    for a in ads:
        s = []
        for f in _frases(a["texto"]):
            pal = _palavras(f)
            s.append((" ".join(pal) if len(pal) >= 3 and len("".join(pal)) >= 10 else None, f))
        seq[a["n"]] = s
        for i, (k, _) in enumerate(s):
            if k:
                onde.setdefault(k, {}).setdefault(a["n"], i)
    rep = {k: d for k, d in onde.items() if len(d) >= 2}
    usados, out = set(), []
    for a in ads:
        s, i = seq[a["n"]], 0
        while i < len(s):
            k = s[i][0]
            if not k or k not in rep or k in usados or min(rep[k]) != a["n"]:
                i += 1
                continue
            grupo, j = [i], i + 1
            while j < len(s):
                kj, ant = s[j][0], s[j - 1][0]
                if (not kj or kj in usados or kj not in rep or set(rep[kj]) != set(rep[k])
                        or any(rep[kj][x] != rep[ant][x] + 1 for x in rep[k])):
                    break
                grupo.append(j); j += 1
            for g in grupo:
                usados.add(s[g][0])
            out.append({"t": " ".join(s[g][1] for g in grupo), "v": len(rep[k]), "a": sorted(rep[k]), "f": len(grupo)})
            i = j
    return sorted(out, key=lambda r: (-r["v"], -r["f"], r["a"]))


def _bloco_igual(texto, trecho, planos_onde):
    """O trecho exato de um elemento, esticado para cima e para baixo: junta as frases vizinhas enquanto o bloco inteiro
    continuar aparecendo igual em TODOS os anúncios onde o trecho aparece (a contagem nunca diminui).
    Devolve (bloco, chave comparável, quantas frases)."""
    plano = lambda t: "".join(_palavras(t))
    alvo, fr = plano(trecho), _frases(texto)
    pl = [plano(f) for f in fr]
    em_todos = lambda i, j: all("".join(pl[i:j + 1]) in t for t in planos_onde)
    # as frases do anúncio que contêm o trecho
    ini = fim = None
    for tam in range(1, 7):                             # a menor janela de frases que contém o trecho
        for i in range(len(fr) - tam + 1):
            if alvo in "".join(pl[i:i + tam]):
                ini, fim = i, i + tam - 1
                break
        if ini is not None:
            break
    if ini is None or not em_todos(ini, fim):          # a frase inteira muda de um anúncio para outro: fica só o trecho
        return trecho.strip(" .…"), alvo, 1
    while ini > 0 and pl[ini - 1] and em_todos(ini - 1, fim):
        ini -= 1
    while fim < len(fr) - 1 and pl[fim + 1] and em_todos(ini, fim + 1):
        fim += 1
    return " ".join(fr[ini:fim + 1]), "".join(pl[ini:fim + 1]), fim - ini + 1


def _proprio(a):
    return _chave(a["origem"]).startswith("propri")


def ofertas_do_expert(v, expert):
    base = v / "Projetos" / expert
    return sorted(p.parent.name for p in base.glob(f"*/{PASTA}") if p.is_dir()) if base.is_dir() else []


def anuncios_expert(v, expert):
    """Anúncios de todas as ofertas do expert, numerados em sequência (a nota guarda o número dentro da oferta)."""
    out = []
    for o in ofertas_do_expert(v, expert):
        for a in anuncios(v, expert, o):
            out.append({**a, "oferta": o, "n_oferta": a["n"], "n": len(out) + 1})
    return out


def _na_base(a, base):
    """base: "" (todos) | "meus" | "validados" (meus, validados) | "concorrentes" | "anunciante:<nome>"."""
    base = str(base or "")
    if base in ("meus", "proprio"):
        return _proprio(a)
    if base == "validados":
        return a["validado"] and _proprio(a)
    if base in ("concorrentes", "concorrente"):
        return not _proprio(a)
    if base.startswith("anunciante:"):
        return _chave(a["anunciante"]) == _chave(base[11:])
    return True


def dados(v, expert, oferta=None, origem=None):
    """Tudo o que a Auditoria mostra, no formato da página do controle de mercado.
    oferta: uma oferta, ou None para todas as do expert. origem: a base (ver _na_base): todos, meus, validados, concorrentes ou um anunciante."""
    todos = [{**a, "oferta": oferta, "n_oferta": a["n"]} for a in anuncios(v, expert, oferta)] if oferta else anuncios_expert(v, expert)
    ads = [a for a in todos if _na_base(a, origem)]
    quem = {}
    for a in todos:
        if not _proprio(a) and a["anunciante"]:
            quem[a["anunciante"]] = quem.get(a["anunciante"], 0) + 1
    planos = {a["n"]: "".join(_palavras(a["texto"])) for a in ads}
    geral = {c[0]: {} for c in CATS}
    ident = {c[0]: {} for c in CATS}
    vistos = {c[0]: set() for c in CATS}
    for a in ads:
        for e in a["elementos"]:
            g = geral[e["cat"]].setdefault(_chave(e["ideia"]), {"t": e["ideia"], "a": set()})
            g["a"].add(a["n"])
            alvo = "".join(_palavras(e["trecho"]))
            if len(alvo) >= 12 and alvo not in vistos[e["cat"]]:
                vistos[e["cat"]].add(alvo)
                onde = sorted(n for n, t in planos.items() if alvo in t)
                if len(onde) >= 2:
                    bloco, chave, frases = _bloco_igual(a["texto"], e["trecho"], [planos[n] for n in onde])
                    if chave not in ident[e["cat"]]:
                        ident[e["cat"]][chave] = {"t": bloco.strip(" …"), "g": e["ideia"], "v": len(onde), "a": onde, "f": frases}
    for c in geral:
        geral[c] = sorted(({"t": x["t"], "v": len(x["a"]), "a": sorted(x["a"])} for x in geral[c].values()), key=lambda r: (-r["v"], r["t"]))
        ident[c] = sorted(ident[c].values(), key=lambda r: (-r["v"], r["t"]))
        nomes = {_chave(x["t"]): x["t"] for x in geral[c]}
        for r in ident[c]:
            r["g"] = nomes.get(_chave(r["g"]), r["g"])

    cat = {}
    for p, t in agentes._notas(v, "Narrativas", "narrativa"):
        est = [re.sub(r"^\s*[-*\d.]+\s*", "", l).strip() for l in agentes._secao(t, "Estrutura").splitlines() if re.match(r"^\s*(?:[-*]|\d+\.)\s+", l)]
        cat[p.stem] = {"grupo": agentes._campos(t).get("grupo", "").strip('"'), "estrutura": est}
    idx = v / "Biblioteca" / "Narrativas" / "Narrativas.md"
    usar = {m.group(1).strip(): m.group(2).strip() for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*[—-]\s*(.+)", idx.read_text(encoding="utf-8"))} if idx.is_file() else {}
    lista, novas = {}, 0
    for a in ads:
        nome = a["narrativa"] or "Sem narrativa"
        if nome not in lista:
            c = cat.get(nome)
            m = re.match(r"(\d+)\s+(.+)", nome)
            if not c:
                novas += 1
            lista[nome] = {"nome": m.group(2) if c and m else re.sub(r"^NOVA:\s*", "", nome), "sig": m.group(1) if c and m else f"N{novas}",
                           "grupo": c["grupo"] if c else "", "nova": not c, "definicao": usar.get(nome, ""),
                           "estrutura": c["estrutura"] if c else [], "ads": []}
        lista[nome]["ads"].append(a["n"])
    narr = {"lista": sorted(lista.values(), key=lambda x: (-len(x["ads"]), x["sig"])),
            "por": {a["n"]: {"formato": a["formato"], "porque": a["porque"], "secundaria": a["secundaria"] or None} for a in ads}}
    arg = _argumentos(ads)
    por_oferta = {}
    for a in anuncios_expert(v, expert):
        por_oferta[a["oferta"]] = por_oferta.get(a["oferta"], 0) + 1
    return {"expert": expert, "oferta": oferta or "", "ofertas": [{"oferta": o, "anuncios": n} for o, n in por_oferta.items()],
            "total": sum(a["copias"] for a in ads),
            "ads": [{"n": a["n"], "oferta": a["oferta"], "n_oferta": a["n_oferta"], "titulo": a["titulo"], "copias": a["copias"], "dur": a["dur"], "tipo": a["formato"], "origem": a["origem"], "validado": a["validado"],
                     "anunciante": a["anunciante"], "texto": a["texto"], "obsidian": link_obsidian(v, a["arq"])} for a in ads],
            "arg": arg, "ident": ident, "geral": geral, "narr": narr if ads else None,
            "proprios": sum(1 for a in todos if _proprio(a)), "concorrentes": sum(1 for a in todos if not _proprio(a)),
            "validados": sum(1 for a in todos if a["validado"] and _proprio(a)), "anunciantes": [{"nome": k, "anuncios": n} for k, n in sorted(quem.items())],
            "obsidian": link_obsidian(v, pasta(v, expert, oferta) / f"{PASTA}.md") if oferta else None}


def experts(v):
    """Experts do cofre que já têm controle de mercado (em qualquer oferta), com os números do cartão."""
    out = []
    for e in sorted(p for p in (v / "Projetos").glob("*") if p.is_dir() and not p.name.startswith(".")):
        ads = anuncios_expert(v, e.name)
        if ads:
            out.append({"expert": e.name, "ofertas": ofertas_do_expert(v, e.name), "videos": sum(a["copias"] for a in ads), "anuncios": len(ads),
                        "argumentos": len(_argumentos(ads)), "proprios": sum(1 for a in ads if _proprio(a)),
                        "atualizado": max(a["arq"].stat().st_mtime for a in ads)})
    return out


def resumo(v, expert, oferta, base=None):
    """O controle de mercado para o agente: classificar anúncio novo com os mesmos nomes de ideia, revisar e criar anúncio.
    Cada ideia vem com quantos anúncios da base a usam e os trechos exatos que mais se repetem."""
    d = dados(v, expert, oferta, base)
    tot = len(d["ads"])
    ideias = {}
    for c in d["geral"]:
        ideias[c] = [{"ideia": x["t"], "anuncios": x["v"], "pct": round(x["v"] / max(1, tot) * 100),
                      "trechos": [f"{i['t']} ({i['v']}x)" for i in d["ident"][c] if i["g"] == x["t"]][:3]} for x in d["geral"][c]]
    return {"base": base or "todos", "anuncios": tot, "na_oferta": {"meus": d["proprios"], "meus_validados": d["validados"], "concorrentes": d["anunciantes"]},
            "ideias": ideias,
            "argumentos_identicos": [{"texto": x["t"][:400], "anuncios": x["v"]} for x in d["arg"][:15]],
            "narrativas": [{"nome": (x["sig"] + " " if not x["nova"] else "NOVA: ") + x["nome"], "anuncios": len(x["ads"])} for x in (d["narr"] or {"lista": []})["lista"]],
            "registrados": [{"n": a["n"], "titulo": a["titulo"], "de": "meu" + (" (validado)" if a["validado"] else "") if _chave(a["origem"]).startswith("propri") else a["anunciante"] or "concorrente",
                             "comeco": a["texto"][:90]} for a in d["ads"]]}


def validar(v, expert, oferta, n, sim):
    """Marca (ou desmarca) um anúncio do controle como validado: status na nota."""
    a = next((x for x in anuncios(v, expert, oferta) if x["n"] == n), None)
    if not a:
        raise ErroControle("anúncio não encontrado")
    props, corpo = ler_fm(a["arq"].read_text(encoding="utf-8"))
    novo = {}
    for k, val in props.items():                      # status logo depois de copias, mesmo em nota antiga
        novo[k] = val
        if k == "copias" and "status" not in props:
            novo["status"] = ""
    novo["status"] = "validado" if sim else ""
    a["arq"].write_text(fm_texto(novo) + corpo, encoding="utf-8")
    return {"n": n, "validado": bool(sim)}


# ---------------- gravar ----------------
def _painel(v, expert, oferta):
    d = dados(v, expert, oferta)
    arqs = {a["n"]: a["arq"].stem for a in anuncios(v, expert, oferta)}
    lk = lambda ns: " ".join(f"[[{arqs[n]}|{n:02d}]]" for n in ns)
    cel = lambda t: str(t).replace("|", "\\|").replace("\n", " ")
    L = [fm_texto({"tipo": "controle_de_mercado", "expert": expert, "oferta": oferta, "videos": d["total"], "anuncios": len(d["ads"]),
                   "trechos_identicos": sum(len(d["ident"][c[0]]) for c in CATS), "atualizado": datetime.date.today().isoformat()}),
         f"# Controle de mercado · {oferta}", "",
         "> Painel escrito pelo Octopus IA a cada alimentação: o que for editado aqui é sobrescrito. A fonte são as notas em `Anúncios/`; a visualização completa fica na aba Criativos › Controle de mercado do Octopus IA.", "",
         f"**{d['total']}** vídeos · **{len(d['ads'])}** anúncios diferentes", ""]
    L += ["## Elementos persuasivos", "", "A ideia, dita de qualquer jeito. *Vezes* conta anúncios diferentes.", ""]
    for c, _, _ in CATS:
        L += [f"### {c}", ""]
        L += (["| Ideia | Vezes | Anúncios |", "|---|---|---|"] + [f"| {cel(x['t'])} | {x['v']} | {lk(x['a'])} |" for x in d["geral"][c]]) if d["geral"][c] else ["Nada registrado."]
        L.append("")
    L += ["## Narrativas", "", "| Narrativa | Anúncios | Quais |", "|---|---|---|"]
    for x in (d["narr"] or {"lista": []})["lista"]:
        nome = f"[[{x['sig']} {x['nome']}]]" if not x["nova"] else f"{x['nome']} (nova)"
        L.append(f"| {nome} | {len(x['ads'])} | {lk(x['ads'])} |")
    L += ["", "## Elementos persuasivos idênticos", ""]
    tem = False
    for c, _, _ in CATS:
        if d["ident"][c]:
            tem = True
            L += [f"### {c}", "", "| Trecho | Ideia | Vezes | Anúncios |", "|---|---|---|---|"] + [f"| “{cel(x['t'])}” | {cel(x['g'])} | {x['v']} | {lk(x['a'])} |" for x in d["ident"][c]] + [""]
    if not tem:
        L.append("Nenhum trecho repetido ainda.")
    arq = pasta(v, expert, oferta) / f"{PASTA}.md"
    arq.write_text("\n".join(L).rstrip("\n") + "\n", encoding="utf-8")
    return arq


def _nova_narrativa(v, nome, ideia, estrutura, exemplo, origem):
    """Cria a nota da narrativa em Biblioteca/Narrativas (número seguinte), a partir do modelo. Devolve o caminho."""
    pasta_n = v / "Biblioteca" / "Narrativas"
    pasta_n.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for p in pasta_n.rglob("*.md") for m in [re.match(r"(\d+)\s", p.stem)] if m]
    n = max(nums or [0]) + 1
    titulo = limpar(nome)[:70]
    arq = pasta_n / f"{n:02d} {titulo}.md"
    mp = v / "Biblioteca" / "Modelos" / "Narrativa.md"
    props, corpo = ler_fm(mp.read_text(encoding="utf-8")) if mp.is_file() else ({}, "# {{title}}\n\n## A ideia\n\n## Estrutura\n\n## Exemplo\n")
    props.update({"tipo": "narrativa", "numero": n, "grupo": "Acrescentadas", "origem": origem, "aliases": [titulo]})
    corpo = re.sub(r"```dataview.*?```", "", corpo, flags=re.S).replace("{{title}}", titulo)
    passos = [x.strip() for x in re.split(r"\s*(?:>|→|;)\s*", estrutura or "") if x.strip()]
    secoes = {"A ideia": ideia or "(a preencher)", "Estrutura": "\n".join(f"{i}. {x}" for i, x in enumerate(passos, 1)) or "(a preencher)", "Exemplo": "> " + exemplo.replace("\n", "\n> ")}
    for sec, t in secoes.items():
        if re.search(rf"^## {re.escape(sec)}[ \t]*$", corpo, re.M):
            corpo = re.sub(rf"^## {re.escape(sec)}[ \t]*\n*", lambda m: f"## {sec}\n\n{t}\n\n", corpo, count=1, flags=re.M)
        else:
            corpo = corpo.rstrip("\n") + f"\n\n## {sec}\n\n{t}\n"
    arq.write_text(fm_texto(props) + re.sub(r"\n{3,}", "\n\n", corpo).rstrip("\n") + "\n", encoding="utf-8")
    return arq


def _swipe(v):
    """Os anúncios de concorrente que moram no Spy: [(caminho, propriedades, texto comparável)]."""
    base, out = v / SWIPE, []
    for p in sorted(base.rglob("*.md")) if base.is_dir() else []:
        props, corpo = ler_fm(p.read_text(encoding="utf-8"))
        if str(props.get("tipo") or "") == "controle_anuncio":
            out.append((p, props, "".join(_palavras(_secao_h2(corpo, "Transcrição")))))
    return out


def _no_swipe(v, titulo, props, corpo, plano):
    """Guarda o anúncio de concorrente no Spy (um arquivo só, para qualquer oferta usar). Se o mesmo anúncio já está lá, usa o que existe."""
    for p, _, pl in _swipe(v):
        if pl == plano:
            return p
    quem = limpar(str(props.get("anunciante") or "Sem nome"))[:60] or "Sem nome"
    pasta_s = v / SWIPE / quem
    pasta_s.mkdir(parents=True, exist_ok=True)
    arq, i = pasta_s / f"{titulo}.md", 2
    while arq.exists():
        arq = pasta_s / f"{titulo} ({i}).md"; i += 1
    comum = {k: val for k, val in props.items() if k not in ("n", "expert", "oferta", "copias", "status")}
    arq.write_text(fm_texto(comum) + re.sub(r"^# .*$", "# " + arq.stem, corpo, count=1, flags=re.M).rstrip("\n") + "\n", encoding="utf-8")
    return arq


def _atalho(v, arq, fonte, n, expert, oferta, anunciante, hoje, copias=1):
    """A nota da oferta que aponta para o anúncio no Spy. Guarda só o que é desta oferta: número, cópias e validado."""
    props = {"tipo": ATALHO, "n": n, "expert": expert, "oferta": oferta, "anunciante": anunciante or "", "alvo": fonte.relative_to(v).as_posix(),
             "copias": copias, "status": "", "data": hoje}
    arq.write_text(fm_texto(props) + f"# {arq.stem}\n\nAnúncio de {anunciante or 'concorrente'} no controle de mercado de {oferta}. O arquivo mora no Spy e pode ser usado por outras ofertas.\n\nAbrir o anúncio: [[{fonte.stem}]]\n", encoding="utf-8")


def no_spy(v, expert, oferta):
    """Por anunciante: quantos anúncios há no Spy e quantos ainda não estão na auditoria desta oferta."""
    tenho = {"".join(_palavras(a["texto"])) for a in anuncios(v, expert, oferta)}
    por = {}
    for p, props, pl in _swipe(v):
        x = por.setdefault(str(props.get("anunciante") or p.parent.name), {"total": 0, "faltam": 0})
        x["total"] += 1
        x["faltam"] += pl not in tenho
    return [{"anunciante": k, **x} for k, x in sorted(por.items())]


def importar(v, expert, oferta, anunciante=None):
    """Traz para a auditoria desta oferta os anúncios de concorrente que já estão no Spy (todos, ou os de um anunciante). Não copia o arquivo: cria o atalho."""
    base = pasta(v, expert, oferta)
    (base / "Anúncios").mkdir(parents=True, exist_ok=True)
    existentes = anuncios(v, expert, oferta)
    tenho = {"".join(_palavras(a["texto"])) for a in existentes}
    num, hoje, novos = max([a["n"] for a in existentes] or [0]), datetime.date.today().isoformat(), 0
    for p, props, pl in _swipe(v):
        quem = str(props.get("anunciante") or p.parent.name)
        if pl in tenho or (anunciante and _chave(quem) != _chave(anunciante)):
            continue
        num += 1; novos += 1; tenho.add(pl)
        _atalho(v, base / "Anúncios" / f"CM {num:02d} - {p.stem[:70]}.md", p, num, expert, oferta, quem, hoje)
    if novos:
        _painel(v, expert, oferta)
    return novos


def levar_para_o_spy(v):
    """Arruma o que foi gravado antes: anúncio de concorrente que ainda mora inteiro dentro da oferta vai para o Spy e vira atalho."""
    mudou = 0
    for nota in sorted((v / "Projetos").glob(f"*/*/{PASTA}/Anúncios/*.md")):
        props, corpo = ler_fm(nota.read_text(encoding="utf-8"))
        if str(props.get("tipo") or "") != "controle_anuncio" or _proprio({"origem": str(props.get("origem") or "")}):
            continue
        fonte = _no_swipe(v, re.sub(r"^CM \d+ - ", "", nota.stem), props, corpo, "".join(_palavras(_secao_h2(corpo, "Transcrição"))))
        _atalho(v, nota, fonte, props.get("n"), props.get("expert"), props.get("oferta"), props.get("anunciante"), str(props.get("data") or ""), props.get("copias") or 1)
        if _chave(props.get("status") or "").startswith("validad"):
            pr, co = ler_fm(nota.read_text(encoding="utf-8")); pr["status"] = "validado"; nota.write_text(fm_texto(pr) + co, encoding="utf-8")
        mudou += 1
    return mudou


def gravar(v, expert, oferta, doc, passo=lambda t: None):
    """Documento tipo: controle-de-mercado → uma nota por anúncio + o painel.
    Anúncio repetido dentro do mesmo documento vira cópia. Anúncio que já estava registrado antes deste envio não é gravado
    nem contado de novo (mandar o mesmo documento duas vezes não pode inflar os vídeos): volta em `ja`, com aviso se a origem for outra."""
    # resposta interrompida e retomada pode trazer o documento colado duas vezes: cada parte é lida separada, e a repetição entre partes não vira cópia
    partes_doc = [p for p in re.split(r"(?m)^(?=---[ \t]*\ntipo:[ \t]*controle-de-mercado)", doc) if p.strip()] or [doc]
    itens = [(t, x, i) for i, p in enumerate(partes_doc) for t, x in _itens(p, "Anúncio")]
    if not itens:
        raise ErroControle('Não achei nenhuma seção "## Anúncio N: …" no documento.')
    base = pasta(v, expert, oferta)
    (base / "Anúncios").mkdir(parents=True, exist_ok=True)
    existentes = anuncios(v, expert, oferta)
    por_texto = {"".join(_palavras(a["texto"])): a for a in existentes}
    num = max([a["n"] for a in existentes] or [0])
    mp = v / MODELO
    modelo = mp.read_text(encoding="utf-8") if mp.is_file() else MODELO_PADRAO
    hoje = datetime.date.today().isoformat()
    unicos = len({t for t, _, _ in itens}) if len(partes_doc) > 1 else len(itens)
    passo(f"Separando {unicos} anúncio{'s' if unicos > 1 else ''}")
    notas, novos, copias, ja, avisos, agora = [], 0, 0, 0, [], {}
    def _fala(txt):
        t = re.sub(r"^```\w*\n|\n```$", "", _secao(txt, "Transcrição").strip()).strip()
        return re.split(r"^[ \t]*(?:---+|# .*)[ \t]*$", t, maxsplit=1, flags=re.M)[0].strip()   # sobra colada depois do último anúncio (outro documento, régua) não é fala
    falas = [_fala(txt) for _, txt, _ in itens]
    planos = ["".join(_palavras(t)) for t in falas]
    for k, (titulo, txt, parte) in enumerate(itens):
        texto, plano = falas[k], planos[k]
        if any(itens[j][2] > parte and planos[j].startswith(plano) for j in range(len(itens))):
            continue                                     # a parte interrompida: o mesmo anúncio vem inteiro na parte seguinte
        if len(texto.split()) < 15:
            raise ErroControle(f'O anúncio "{titulo}" veio sem a transcrição inteira.')
        if plano in agora and agora[plano] != parte:     # o mesmo anúncio na outra metade de um documento colado duas vezes
            continue
        if plano in por_texto and plano not in agora:    # já estava no controle antes deste envio: não grava nem conta de novo
            a = por_texto[plano]
            agora[plano] = parte
            ja += 1
            notas.append({"caminho": a["arq"].relative_to(v).as_posix(), "nova": False, "ja": True})
            veio, quem = _campo(txt, "Origem").lower() or "concorrente", _campo(txt, "Anunciante")
            era = "seu" if _proprio(a) else f"de {a.get('anunciante') or 'concorrente'}"
            if _proprio({"origem": veio}) != _proprio(a) or (not _proprio(a) and quem and _chave(quem) != _chave(a.get("anunciante") or "")):
                avisos.append(f'"{titulo}" tem a mesma fala de um anúncio que já está registrado como {era} ({a["arq"].stem}). Ficou como estava.')
            continue
        agora[plano] = parte
        if plano in por_texto:                           # o mesmo anúncio repetido neste documento: só soma a cópia
            a = por_texto[plano]
            props, corpo = ler_fm(a["arq"].read_text(encoding="utf-8"))
            props["copias"] = a["copias"] + 1
            a["copias"] += 1
            a["arq"].write_text(fm_texto(props) + corpo, encoding="utf-8")
            notas.append({"caminho": a["arq"].relative_to(v).as_posix(), "nova": False})
            copias += 1
            continue
        els = []
        for l in _secao(txt, "Elementos").splitlines():
            p = [x.strip() for x in re.sub(r"^\s*[-*]\s*", "", l).split("|")]
            if len(p) >= 2 and _categoria(p[0]) and p[1]:
                els.append((_categoria(p[0]), p[1].strip(" .\"“”"), (p[2] if len(p) > 2 else "").strip(" .\"“”…")))
        if not els:
            raise ErroControle(f'O anúncio "{titulo}" veio sem a seção Elementos.')
        num += 1
        narr = _campo(txt, "Narrativa")
        nome_narr = re.sub(r"^NOVA:\s*", "", narr or "", flags=re.I).strip()
        achou = agentes._achar_nota(agentes._notas(v, "Narrativas", "narrativa"), nome_narr) if nome_narr else None
        if not achou and nome_narr and re.match(r"NOVA", narr, re.I):
            # narrativa que não existe no catálogo: vira nota na Biblioteca, e passa a valer para todas as ofertas
            nova = _nova_narrativa(v, nome_narr, _campo(txt, "Ideia da narrativa"), _campo(txt, "Estrutura da narrativa"), texto, f"controle de mercado de {oferta} ({expert})")
            achou = (nova, "")
        sec = _campo(txt, "Narrativa secundária")
        achou2 = agentes._achar_nota(agentes._notas(v, "Narrativas", "narrativa"), sec) if sec and not re.match(r"NOVA|nenhuma|-|—", sec, re.I) else None
        dur = re.search(r"\d+", _campo(txt, "Duração"))
        props, corpo = ler_fm(modelo)
        um = {c[0]: c[2] for c in CATS}
        props.update({"tipo": "controle_anuncio", "n": num, "expert": expert, "oferta": oferta, "origem": _campo(txt, "Origem").lower() or "concorrente",
                      "status": "validado" if _chave(_campo(txt, "Status")).startswith("validad") else "",
                      "anunciante": _campo(txt, "Anunciante"), "copias": 1, "duracao": int(dur.group()) if dur else round(len(texto.split()) / agentes.PPM * 60),
                      "narrativa": f"[[{achou[0].stem}]]" if achou else ("NOVA: " + re.sub(r"^NOVA:\s*", "", narr, flags=re.I) if narr else ""),
                      "narrativa_secundaria": f"[[{achou2[0].stem}]]" if achou2 else ("" if re.match(r"nenhuma|-|—", sec or "-", re.I) else sec),
                      "formato": _campo(txt, "Formato"), "data": hoje})
        for nome, prop, _ in CATS:
            vistos = []
            for c, ideia, _t in els:
                if c == nome and _chave(ideia) not in [_chave(x) for x in vistos]:
                    vistos.append(ideia)
            props[prop] = vistos
        arq = base / "Anúncios" / f"CM {num:02d} - {limpar(titulo)[:70]}.md"
        secoes = {"Por que esta narrativa": _campo(txt, "Por quê") or _campo(txt, "Por que"),
                  "Elementos persuasivos": "\n".join(f"- **{um[c]}** · {i}" + (f" — “{t}”" if t else "") for c, i, t in els),
                  "Transcrição": texto}
        corpo = corpo.replace("{{title}}", arq.stem).replace("{{date}}", hoje)
        for nome, t in secoes.items():
            if re.search(rf"^## {re.escape(nome)}[ \t]*$", corpo, re.M):
                corpo = re.sub(rf"^## {re.escape(nome)}[ \t]*\n*", lambda m: f"## {nome}\n\n{t}\n\n", corpo, count=1, flags=re.M)
            else:
                corpo = corpo.rstrip("\n") + f"\n\n## {nome}\n\n{t}\n"
        if _proprio({"origem": props["origem"]}):
            arq.write_text(fm_texto(props) + corpo.rstrip("\n") + "\n", encoding="utf-8")
        else:
            fonte = _no_swipe(v, limpar(titulo)[:70], props, corpo, plano)
            _atalho(v, arq, fonte, num, expert, oferta, props.get("anunciante"), hoje)
        por_texto[plano] = {"arq": arq, "copias": 1, "origem": props["origem"], "anunciante": props.get("anunciante") or ""}
        notas.append({"caminho": arq.relative_to(v).as_posix(), "nova": True})
        novos += 1
    passo("Recontando o controle de mercado")
    painel = _painel(v, expert, oferta)
    pl = lambda n, um, mais: f"{n} {um if n == 1 else mais}"
    partes = ([pl(novos, "anúncio novo", "anúncios novos")] if novos else []) + ([pl(copias, "cópia somada", "cópias somadas")] if copias else [])
    if ja:
        partes.append(pl(ja, "já estava no controle", "já estavam no controle") if partes else ("Nada novo: o anúncio já estava no controle" if ja == 1 else f"Nada novo: os {ja} anúncios já estavam no controle"))
    return {"caminho": painel.relative_to(v).as_posix(), "obsidian": link_obsidian(v, painel), "notas": notas, "novos": novos, "copias": copias,
            "ja": ja, "avisos": avisos, "resumo": ", ".join(partes)}
