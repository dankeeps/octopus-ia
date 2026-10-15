"""O índice do Cérebro: lê todas as notas da pasta de arquivos do Octopus IA e monta, em memória,
as propriedades e as ligações de cada nota:

    notas(v)                      cada nota com propriedades, ligações que saem e de onde é
    consultar(v, ...)             consulta por tipo, pasta, propriedade e texto (para a tela e para os agentes)
    ler(v, caminho)               uma nota inteira, com propriedades e "citada em"
    grafo(v)                      nós e ligações para o grafo, com a cabeça no centro e os oito braços

Nada é guardado em banco: a fonte são os arquivos .md. O resultado fica em memória e é refeito quando algum arquivo muda.
"""
import re, time
from pathlib import Path

from spy import ler_fm

LIGACAO = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_cache = {"chave": None, "notas": None}


def _arquivos(v):
    for p in v.rglob("*.md"):
        rel = p.relative_to(v).parts
        if any(x.startswith(".") for x in rel) or "Atlas" in rel[:-1]:      # ocultas e as notas internas do app (flows, conversas)
            continue
        yield p


def notas(v):
    """Lista de notas: caminho, nome, pasta, tipo, propriedades, ligações (caminhos) e tamanho."""
    arqs = list(_arquivos(v))
    chave = (str(v), len(arqs), max((p.stat().st_mtime_ns for p in arqs), default=0))
    if _cache["chave"] == chave:
        return _cache["notas"]
    por_nome, brutas = {}, []
    for p in arqs:
        texto = p.read_text(encoding="utf-8", errors="replace")
        props, corpo = ler_fm(texto)
        rel = p.relative_to(v).as_posix()
        por_nome.setdefault(p.stem.lower(), rel)
        alvos = set(LIGACAO.findall(corpo))
        for k, val in props.items():                        # ligação também vale dentro das propriedades (narrativa: "[[…]]")
            for x in (val if isinstance(val, list) else [val]):
                alvos.update(LIGACAO.findall(str(x)))
                if k in LIGA_PELO_NOME and isinstance(x, str) and x.strip() and "[[" not in x:      # e pelo nome puro (formato: "Fala para a câmera")
                    alvos.add(x.strip().strip('"'))
        titulo = re.search(r"^# (.+)$", corpo, re.M)
        brutas.append({"caminho": rel, "nome": p.stem, "titulo": titulo.group(1).strip() if titulo else p.stem, "pasta": "/".join(rel.split("/")[:-1]),
                       "tipo": str(props.get("tipo") or "").strip('"'), "props": props, "_alvos": alvos, "caracteres": len(corpo),
                       "mexida": int(p.stat().st_mtime)})
    # a VSL de cada oferta, por versão: o anúncio se liga a ela pela propriedade vsl ("V1"), sem precisar de [[ ]]
    oferta_de = lambda n: (str(n["props"].get("expert") or "").strip('"').lower(), str(n["props"].get("oferta") or "").strip('"').lower())
    vsls = {(*oferta_de(n), _versao(n["props"].get("versao"))): n["caminho"] for n in brutas if n["tipo"] == "vsl"}
    for n in brutas:
        liga = {por_nome[a.strip().lower()] for a in n.pop("_alvos") if a.strip().lower() in por_nome}
        if n["tipo"] == "anuncio" and n["props"].get("vsl"):
            alvo = vsls.get((*oferta_de(n), _versao(n["props"].get("vsl"))))
            if alvo:
                liga.add(alvo)
        n["ligacoes"] = sorted(liga - {n["caminho"]})
    _cache.update(chave=chave, notas=brutas)
    return brutas


LIGA_PELO_NOME = ("narrativa", "formato", "angulo", "persona", "big_idea", "tipo_hook")


def _versao(x):
    m = re.search(r"(\d+)", str(x or ""))
    return f"V{int(m.group(1))}" if m else ""


def _limpo(x):
    return re.sub(r"^\[\[|\]\]$", "", str(x)).split("|")[0].strip().strip('"').lower()


def _bate(valor, quer):
    quer = _limpo(quer)
    vals = valor if isinstance(valor, list) else [valor]
    return any(quer == _limpo(v) or (len(quer) > 2 and quer in _limpo(v)) for v in vals if v is not None)


def consultar(v, tipo=None, pasta=None, onde=None, texto=None, limite=60, base=None):
    """Consulta as notas. onde = {propriedade: valor}. base = pastas permitidas (chat preso a uma oferta)."""
    out = []
    quer_txt = str(texto or "").strip().lower()
    for n in notas(v):
        if base and not any(n["caminho"].startswith(b) for b in base):
            continue
        if tipo and _limpo(tipo).replace("-", "_") != n["tipo"].lower().replace("-", "_"):
            continue
        if pasta and not n["caminho"].lower().startswith(str(pasta).strip("/").lower()):
            continue
        if onde and not all(_bate(n["props"].get(k), val) for k, val in onde.items()):
            continue
        if quer_txt and quer_txt not in n["nome"].lower() and quer_txt not in (v / n["caminho"]).read_text(encoding="utf-8", errors="replace").lower():
            continue
        out.append({"caminho": n["caminho"], "tipo": n["tipo"], **{k: val for k, val in n["props"].items() if k != "tipo"}})
    total = len(out)
    return {"total": total, "notas": out[:max(1, min(200, int(limite or 60)))]}


def ler(v, caminho):
    todas = notas(v)
    n = next((x for x in todas if x["caminho"] == caminho), None)
    if not n:
        return None
    _, corpo = ler_fm((v / caminho).read_text(encoding="utf-8", errors="replace"))
    tipo_de = {x["caminho"]: x["tipo"] for x in todas}
    # anúncio aberto: os outros criativos que mandam para a mesma VSL
    minha_vsl = next((c for c in n["ligacoes"] if tipo_de.get(c) == "vsl"), None) if n["tipo"] == "anuncio" else None
    irmaos = [{"caminho": x["caminho"], "nome": x["nome"], "tipo": x["tipo"]} for x in todas
              if minha_vsl and x["tipo"] == "anuncio" and x["caminho"] != caminho and minha_vsl in x["ligacoes"]]
    return {"caminho": n["caminho"], "nome": n["nome"], "tipo": n["tipo"], "props": n["props"], "corpo": corpo,
            "liga_para": [{"caminho": c, "nome": Path(c).stem, "tipo": tipo_de.get(c, "")} for c in n["ligacoes"]],
            "citada_em": [{"caminho": x["caminho"], "nome": x["nome"], "tipo": x["tipo"]} for x in todas if caminho in x["ligacoes"]],
            "irmaos": sorted(irmaos, key=lambda x: x["nome"])}


# ---------------- o grafo ----------------
# os oito braços: (id, nome, como reconhecer a nota)
BRACOS = [("narrativas", "Narrativas"), ("formatos", "Formatos"), ("angulos", "Ângulos"), ("modelos", "Modelos"),
          ("regras", "Regras e exemplos"), ("ofertas", "Ofertas"), ("auditoria", "Controle de mercado"), ("spy", "Spy")]


def _braco(n):
    c, t = n["caminho"], n["tipo"]
    if c.startswith("Biblioteca/Narrativas/"): return "narrativas", n["props"].get("grupo") or ""
    if c.startswith("Biblioteca/Formatos/"): return "formatos", n["props"].get("categoria") or ""
    if c.startswith("Biblioteca/Ângulos/"): return "angulos", n["props"].get("categoria") or ""
    if c.startswith("Biblioteca/Modelos/"): return "modelos", ""
    if c.startswith("Biblioteca/"): return "regras", ""
    if c.startswith("Swipe/"): return "spy", (c.split("/")[2] if c.count("/") > 2 else "")
    if c.startswith("Projetos/"):
        p = c.split("/")
        oferta = " · ".join(p[1:3]) if len(p) > 3 else (p[1] if len(p) > 2 else "")
        return ("auditoria" if "Controle de mercado" in p else "ofertas"), oferta
    return "regras", ""


def grafo(v):
    """Nós e ligações. A cabeça (o Octopus) no centro; um braço por área; subgrupos (categoria, oferta) no meio do braço; as notas na ponta."""
    nos = [{"id": "@centro", "nome": "Octopus IA", "g": "centro", "nivel": 0}]
    lig, sub = [], {}
    for bid, nome in BRACOS:
        nos.append({"id": "@" + bid, "nome": nome, "g": bid, "nivel": 1})
        lig.append({"a": "@centro", "b": "@" + bid, "t": "braco"})
    for n in notas(v):
        bid, grupo = _braco(n)
        grupo = str(grupo).strip('"')
        pai = "@" + bid
        if grupo:
            sid = f"@{bid}/{grupo}"
            if sid not in sub:
                sub[sid] = True
                nos.append({"id": sid, "nome": grupo, "g": bid, "nivel": 2})
                lig.append({"a": pai, "b": sid, "t": "braco"})
            pai = sid
        nos.append({"id": n["caminho"], "nome": n["nome"], "g": bid, "nivel": 3, "tipo": n["tipo"], "n": len(n["ligacoes"])})
        lig.append({"a": pai, "b": n["caminho"], "t": "braco"})
        for alvo in n["ligacoes"]:
            lig.append({"a": n["caminho"], "b": alvo, "t": "link"})
    return {"nos": nos, "ligacoes": lig, "bracos": [{"id": b, "nome": nome} for b, nome in BRACOS], "notas": len(notas(v))}


# ---------------- a árvore do Cérebro (as quatro pastas) ----------------
SEM_MODELO = "(pensar no modelo)"
ORDEM_MODELOS = ["Bíblia do nicho", "Cruzamento de raio-X", "Briefing de tese", "VSL", "Anúncio", "Big idea", "Persona", "Dicionário da oferta", "Anúncio do controle de mercado",
                 "Narrativa", "Formato", "Ângulo", "Estrutura de VSL", "Spy página", "Relatório de Spy", "Credenciais", "História"]


def _arq(p, v, nome=None):
    return {"nome": nome or p.stem, "caminho": p.relative_to(v).as_posix()}


def _arqs(pasta, v):
    return [_arq(p, v) for p in sorted(pasta.glob("*.md"), key=lambda x: x.name.lower())] if pasta.is_dir() else []


def _pasta(nome, filhos, obs=""):
    return {"nome": nome, "filhos": filhos, **({"obs": obs} if obs else {})}


def validados(v, o):
    """Os anúncios do próprio expert marcados como validados na auditoria da oferta: já existiam, foram só catalogados."""
    try:
        import controle
        ads = controle.anuncios(v, o.parent.name, o.name)
    except Exception:
        return []
    return [{"nome": a["titulo"], "caminho": a["arq"].relative_to(v).as_posix(), "palavras": len(str(a.get("texto") or "").split())}
            for a in ads if a.get("validado") and str(a.get("origem") or "").lower().startswith("pr") and a.get("arq") and v in a["arq"].parents]


def _oferta(v, o):
    cm = o / "Controle de mercado"
    mapa = [_pasta("Controle de mercado", _arqs(cm, v) + _arqs(cm / "Anúncios", v)),
            _pasta("Persona", _arqs(o / "Personas", v))]
    dic = o / "Dicionário da oferta.md"
    mapa.append(_arq(dic, v) if dic.is_file() else {"nome": "Dicionário da oferta", "obs": "(ainda não criado)"})
    return {"dir": o.relative_to(v).as_posix(), **_pasta(o.name, [
        _pasta("VSL", _arqs(o / "VSL", v)),
        _pasta("Criativos", [_pasta("Validados", [{"nome": x["nome"], "caminho": x["caminho"]} for x in validados(v, o)])] + [_pasta(r.name, _arqs(r, v)) for r in sorted((o / "Anúncios").glob("Remessa *")) if r.is_dir()] + _arqs(o / "Anúncios", v)),
        _pasta("Big ideas", _arqs(o / "Big ideas", v)),
        _pasta("Mapa do mercado", mapa)])}


def _exemplo():
    m = lambda nome, modelo, obs="": {"nome": nome, "caminho": f"Biblioteca/Modelos/{modelo}.md", **({"obs": obs} if obs else {})}
    return _pasta("Exemplo", [
        _pasta("Nome do expert", [m("Credenciais", "Credenciais"), m("História", "História")]),
        _pasta("Nome da oferta", [
            _pasta("VSL", [m("Bíblia do nicho", "Bíblia do nicho"), m("Briefing de tese", "Briefing de tese"), m("VSL V1", "VSL")]),
            _pasta("Criativos", [_pasta("Remessa 01", [m("AD01 a AD10", "Anúncio")], SEM_MODELO)]),
            _pasta("Big ideas", [m("Big idea", "Big idea")]),
            _pasta("Mapa do mercado", [m("Controle de mercado", "Anúncio do controle de mercado"), m("Persona", "Persona"),
                                       m("Dicionário da oferta", "Dicionário da oferta")])])], "modelo da estrutura")


def arvore(v, skills, semente=None):
    """As quatro pastas da aba Cérebro: Octopus Intelligence (skills), Modelos, Biblioteca e Projetos."""
    intel = []
    for p in sorted(skills.glob("*/SKILL.md")) if skills.is_dir() else []:
        m = re.search(r"^# (.+)$", p.read_text(encoding="utf-8", errors="replace"), re.M)
        intel.append({"nome": m.group(1).strip() if m else p.parent.name, "caminho": f"@skill/{p.parent.name}"})
    bib = v / "Biblioteca"
    mods = {p.stem: p for p in (bib / "Modelos").glob("*.md")} if (bib / "Modelos").is_dir() else {}
    rotulo = {"Anúncio": "Copy de anúncio", "VSL": "VSL da oferta"}      # no menu, o modelo aparece com o nome do agente que o usa
    modelos = [_arq(mods[n], v, rotulo.get(n)) for n in ORDEM_MODELOS if n in mods] + [_arq(p, v) for n, p in sorted(mods.items()) if n not in ORDEM_MODELOS]
    biblioteca = [_pasta(n, _arqs(bib / n, v)) for n in ("Narrativas", "Formatos", "Ângulos", "Ganchos", "Estruturas de VSL") if (bib / n).is_dir()]
    for arq, nome in (("Palavras-chave Spy.md", "Palavras-chave"), ("Vícios de IA.md", "Vícios de IA"), ("Gatilhos do interesse.md", "Gatilhos do interesse"), ("Tom argumentativo.md", "Tom argumentativo")):
        if (bib / arq).is_file():
            biblioteca.append(_arq(bib / arq, v, nome))
    ok = lambda p: p.is_dir() and not p.name.startswith(".") and p.name != "Atlas"
    projetos = []
    base = v / "Projetos"
    for e in sorted((p for p in base.iterdir() if ok(p)), key=lambda x: x.name.lower()) if base.is_dir() else []:
        f = [_arq(e / f"{n}.md", v) if (e / f"{n}.md").is_file() else {"nome": n, "obs": "(ainda não criado)"} for n in ("Credenciais", "História")]
        projetos.append({"dir": e.relative_to(v).as_posix(), **_pasta(e.name, [{"nome": "Checklist", "acao": "checklist", "expert": e.name}] + f + [_oferta(v, o) for o in sorted((p for p in e.iterdir() if ok(p)), key=lambda x: x.name.lower())]
                               + [{"nome": "Nova oferta", "acao": "nova-oferta", "expert": e.name}])})
    projetos.append({"nome": "Novo expert", "acao": "novo-expert"})
    def arvore_de(pasta):                       # pastas e notas, em qualquer profundidade
        if not pasta.is_dir():
            return []
        subs = [{**_pasta(d.name, arvore_de(d)), "dir": d.relative_to(v).as_posix()} for d in sorted((x for x in pasta.iterdir() if ok(x)), key=lambda x: x.name.lower())]
        return subs + _arqs(pasta, v)

    def apagavel(no):                           # os três pontinhos: tudo o que é arquivo ou pasta de verdade dentro de Experts e do Spy
        if no.get("caminho") or no.get("dir"):
            no["apaga"] = True
        for f in no.get("filhos") or []:
            apagavel(f)
        return no
    # na Biblioteca só dá para excluir o que foi criado depois (o que veio com o Octopus IA fica)
    for grupo in biblioteca:
        for f in grupo.get("filhos") or []:
            c = f.get("caminho")
            if c and semente is not None and not (semente / Path(c).relative_to("Biblioteca")).exists():
                f["apaga"] = True
    spy = [apagavel(x) if x.get("caminho") not in ("Swipe/Spy/Spy.md", "Swipe/Spy/Blacklist.md") else x for x in arvore_de(v / "Swipe" / "Spy")]
    conc = [apagavel(x) for x in arvore_de(v / "Swipe" / "Auditoria")]
    for e in projetos:
        if e.get("filhos") is not None:
            apagavel(e)
    return [_pasta("Octopus Intelligence", intel), _pasta("Modelos", modelos), _pasta("Biblioteca", biblioteca), _pasta("Experts", projetos),
            _pasta("Spy", spy + ([_pasta("Anúncios de concorrentes", conc)] if (v / "Swipe" / "Auditoria").is_dir() else [])), {"nome": "Ficheiro", "acao": "ficheiro"}]


def ler_skill(skills, nome):
    p = skills / nome / "SKILL.md"
    if not re.fullmatch(r"[a-z0-9-]+", nome or "") or not p.is_file():
        return None
    props, corpo = ler_fm(p.read_text(encoding="utf-8", errors="replace"))
    return {"caminho": f"@skill/{nome}", "nome": nome, "tipo": "skill", "props": {"tipo": "skill", "descrição": props.get("description") or ""},
            "corpo": corpo, "liga_para": [], "citada_em": []}


def ficha_do_expert(v, expert):
    """Credenciais e História do expert, a partir dos modelos. Não mexe no que já existe."""
    import datetime
    hoje = datetime.date.today().isoformat()
    for n in ("Credenciais", "História"):
        alvo, mod = v / "Projetos" / expert / f"{n}.md", v / "Biblioteca" / "Modelos" / f"{n}.md"
        if alvo.exists() or not mod.is_file():
            continue
        t = mod.read_text(encoding="utf-8").replace("{{title}}", expert).replace("{{date}}", hoje).replace('expert: ""', f'expert: "{expert}"')
        alvo.write_text(t, encoding="utf-8")


def checklist(v, expert):
    """O que cada oferta do expert já tem do checklist de montagem: dicionário da oferta, mapa de mercado e personas."""
    rel = lambda p: p.relative_to(v).as_posix()
    ok = lambda p: p.is_dir() and not p.name.startswith(".") and p.name != "Atlas"
    base, ofertas = v / "Projetos" / expert, []
    for o in sorted((p for p in base.iterdir() if ok(p)), key=lambda x: x.name.lower()) if base.is_dir() else []:
        dic, cm = o / "Dicionário da oferta.md", o / "Controle de mercado"
        ads = sorted((cm / "Anúncios").glob("*.md")) if (cm / "Anúncios").is_dir() else []
        painel = cm / "Controle de mercado.md"
        pers = sorted((o / "Personas").glob("*.md")) if (o / "Personas").is_dir() else []
        ofertas.append({"oferta": o.name, "itens": [
            {"id": "dicionario", "feito": dic.is_file(), "qtd": 1 if dic.is_file() else 0, "notas": [rel(dic)] if dic.is_file() else []},
            {"id": "mapa", "feito": bool(ads), "qtd": len(ads), "notas": [rel(painel)] if painel.is_file() else []},
            {"id": "avatar", "feito": bool(pers), "qtd": len(pers), "notas": [rel(p) for p in pers]}]})
    def preenchida(p):
        """Credenciais e História nascem do modelo, só com os títulos e as dicas: conta como feita quando alguém escreveu nela."""
        if not p.is_file():
            return False
        _, corpo = ler_fm(p.read_text(encoding="utf-8", errors="replace"))
        return sum(len(l.strip()) for l in corpo.splitlines() if l.strip() and not l.lstrip().startswith(("#", ">"))) > 15
    ficha_do_expert(v, expert)
    do_expert = [{"id": i, "feito": preenchida(base / f"{n}.md"), "qtd": 0, "notas": [rel(base / f"{n}.md")] if (base / f"{n}.md").is_file() else []}
                 for i, n in (("credenciais", "Credenciais"), ("historia", "História"))]
    return {"expert": expert, "do_expert": do_expert, "ofertas": ofertas}
