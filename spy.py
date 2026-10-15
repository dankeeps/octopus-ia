"""Spy do Octopus IA: roda o coletor (spy/coletor.mjs) e grava o resultado no Cérebro (a pasta de arquivos do Octopus IA).

No cofre:
    Biblioteca/Palavras-chave Spy.md        palavras por nicho (português, inglês, Latam)
    Biblioteca/Modelos/Spy página.md        modelo da nota de cada biblioteca
    Biblioteca/Modelos/Relatório de Spy.md  modelo do relatório de cada busca
    Swipe/Spy/Spy.md · Blacklist.md
    Swipe/Spy/Relatórios/Spy AAAA-MM-DD <Nicho>.md
    Swipe/Spy/<Nicho>/<Página> (Spy)/<Página> (Spy).md  + Criativos/ + Funil/

A mesma página (mesmo page_id ou mesmo nome) é atualizada, não duplicada; o mesmo dia não
se repete no histórico; página na blacklist não entra. A pesquisa não gasta IA.
"""
import datetime, json, re, secrets, shutil, subprocess, threading, time, urllib.parse
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
from locais import LOCAL, env_filho
PASTA = LOCAL / "spy"
BUSCAS = PASTA / "buscas"
COLETOR = RAIZ / "spy" / "coletor.mjs"
PAISES = {"BR", "PT", "US", "MX", "CO", "ES", "AR", "CL", "PE", "ALL"}

MODELO_PAGINA = "Biblioteca/Modelos/Spy página.md"
MODELO_RELATORIO = "Biblioteca/Modelos/Relatório de Spy.md"
PALAVRAS = "Biblioteca/Palavras-chave Spy.md"


class ErroSpy(Exception):
    pass


# ---------------- frontmatter simples (as notas do Spy só têm texto, número, sim/não e listas) ----------------
SEM_NICHO = "Nicho a definir"      # biblioteca salva sem nicho escolhido: a pessoa acerta em Bibliotecas


def _valor(v):
    v = v.strip()
    if v == "":
        return None
    if v in ("true", "false"):
        return v == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if v.startswith("[") and v.endswith("]"):
        try:
            return json.loads(v)
        except ValueError:
            return [x.strip().strip('"\'') for x in v[1:-1].split(",") if x.strip()]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        try:
            return json.loads(v) if v[0] == '"' else v[1:-1]
        except ValueError:
            return v[1:-1]
    return v


def ler_fm(texto):
    """(propriedades em ordem, corpo)."""
    if not texto.startswith("---"):
        return {}, texto
    fim = texto.find("\n---", 3)
    if fim == -1:
        return {}, texto
    props, chave = {}, None
    for l in texto[3:fim].strip("\n").splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", l)
        if m:
            chave = m.group(1)
            props[chave] = _valor(m.group(2))
        elif chave and re.match(r"^\s+-\s*", l):
            if not isinstance(props.get(chave), list):
                props[chave] = []
            props[chave].append(_valor(re.sub(r"^\s+-\s*", "", l)))
    corpo = texto[fim + 4:]
    return props, corpo[1:] if corpo.startswith("\n") else corpo


def fm_texto(props):
    linhas = ["---"]
    for k, v in props.items():
        if isinstance(v, bool):
            linhas.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            linhas.append(f"{k}: {v}")
        elif v is None:
            linhas.append(f"{k}:")
        elif isinstance(v, list):
            linhas.append(f"{k}: []" if not v else f"{k}:\n" + "\n".join(f"  - {json.dumps(str(x), ensure_ascii=False)}" for x in v))
        else:
            linhas.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    return "\n".join(linhas) + "\n---\n"


def limpar(nome):
    nome = re.sub(r'[/\\:*?"<>|#^\[\]]', " ", str(nome or ""))
    nome = re.sub(r"\s+", " ", nome).strip().strip(".")
    from locais import nome_windows
    return nome_windows(nome[:80]) or "Sem nome"


def page_id(link):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(link or "").query)
    for k in ("view_all_page_id", "page_id"):
        if q.get(k):
            return q[k][0]
    return ""


def link_obsidian(v, caminho):
    rel = caminho.relative_to(v).as_posix()
    return "obsidian://open?" + urllib.parse.urlencode({"vault": v.name, "file": rel[:-3]}, quote_via=urllib.parse.quote)


# ---------------- o cofre ----------------
PAINEL = """---
tipo: "indice"
---

# Spy

As bibliotecas de anúncio achadas pelo Spy do Octopus IA, por nicho, com o histórico de
anúncios ativos. Palavras usadas: [[Palavras-chave Spy]]. O que nunca deve entrar:
[[Blacklist]].

Estrutura: `Spy / <Nicho> / <Página> (Spy) /` com a nota da página e as pastas
**Criativos** (os anúncios que você salvar) e **Funil** (VSL, quiz, página). Para
acompanhar uma biblioteca em toda busca, ligue o monitoramento na aba Spy › Bibliotecas do Octopus IA.

## Onde ver

As bibliotecas, as monitoradas e os relatórios aparecem na aba **Spy › Bibliotecas** do Octopus IA.
"""

BLACKLIST = """---
tipo: "spy_blacklist"
---

# Blacklist

Páginas que o Spy nunca salva no Cérebro, mesmo aparecendo na pesquisa. Uma por
linha: o nome da página (ou `—`), o `page_id` do link da biblioteca (ou `—`), o motivo
e a data.

| Página | page_id | Motivo | Desde |
|---|---|---|---|
"""

# usados só se o cofre não tiver os modelos
PAGINA_PADRAO = """---
tipo: spy_pagina
nicho: ""
pagina: ""
link_biblioteca: ""
page_id: ""
anuncios_ativos:
variacao: 0
primeira_verificacao: "{{date}}"
ultima_verificacao: "{{date}}"
monitoramento: false
palavras_chave: []
historico: []
---
# {{title}}

Biblioteca de anúncios achada pelo Spy. O histórico cresce a cada Spy que encontra esta
página. Para acompanhar em toda busca, mude `monitoramento` para `true`.

## Histórico de anúncios ativos

## Criativos

## Funil
"""
RELATORIO_PADRAO = """---
tipo: spy_relatorio
data: "{{date}}"
nicho: ""
palavras_buscadas: []
bibliotecas_encontradas:
novas:
anuncios_total:
ignoradas_blacklist:
---
# {{title}}

| Página | Anúncios ativos | Variação | Monitorada | Palavra | Biblioteca |
|---|---|---|---|---|---|
"""


def pasta_spy(v):
    spy = v / "Swipe" / "Spy"
    spy.mkdir(parents=True, exist_ok=True)
    if not (spy / "Spy.md").exists():
        (spy / "Spy.md").write_text(PAINEL, encoding="utf-8")
    if not (spy / "Blacklist.md").exists():
        (spy / "Blacklist.md").write_text(BLACKLIST, encoding="utf-8")
    return spy


def modelo(v, rel, padrao):
    p = v / rel
    return p.read_text(encoding="utf-8") if p.is_file() else padrao


def preencher(texto_modelo, titulo, valores, extra=None):
    """Encaixa no modelo do cofre: as propriedades seguem a ordem do modelo, o corpo é o do modelo."""
    props, corpo = ler_fm(texto_modelo)
    for k, val in valores.items():
        props[k] = val                      # chave que o modelo não tem entra no fim
    corpo = corpo.replace("{{title}}", titulo).replace("{{date}}", valores.get("data") or datetime.date.today().isoformat())
    for k, val in (extra or {}).items():
        corpo = corpo.replace("{{" + k + "}}", val)
    return fm_texto(props) + corpo


def blacklist(spy):
    p = spy / "Blacklist.md"
    itens = set()
    if p.exists():
        for l in p.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|", l)
            if m and m.group(1) not in ("Página", "---", ""):
                for x in (m.group(1), m.group(2)):
                    if x and x not in ("—", "-") and not x.startswith("---"):
                        itens.add(x.lower())
    return itens


def na_blacklist(bl, pagina, link, pid=""):
    pid = pid or page_id(link)
    return pagina.lower() in bl or (pid and pid.lower() in bl)


def paginas(v):
    spy = v / "Swipe" / "Spy"
    if not spy.is_dir():
        return
    for p in spy.rglob("*.md"):
        if ".trash" in p.parts:
            continue
        try:
            pr, _ = ler_fm(p.read_text(encoding="utf-8"))
        except OSError:
            continue
        if pr.get("tipo") == "spy_pagina":
            yield p, pr


def achar(v, pagina, pid):
    for p, pr in paginas(v):
        if (pid and str(pr.get("page_id") or "") == pid) or str(pr.get("pagina") or "").lower() == pagina.lower():
            return p
    return None


def registrar(v, spy, nicho, r, data):
    """Cria ou atualiza a nota da página. Devolve (situação, caminho, anúncios do Spy anterior)."""
    pagina, link = limpar(r["pagina"]), r.get("link") or ""
    pid = r.get("page_id") or page_id(link)
    anuncios = int(r.get("anuncios") or 0)
    palavras = [x for x in r.get("palavras") or [] if x]
    p = achar(v, pagina, pid)
    if p is None:
        pasta = spy / limpar(nicho) / f"{pagina} (Spy)"
        (pasta / "Criativos").mkdir(parents=True, exist_ok=True)
        (pasta / "Funil").mkdir(parents=True, exist_ok=True)
        p = pasta / f"{pagina} (Spy).md"
        valores = {"tipo": "spy_pagina", "nicho": nicho, "pagina": pagina, "link_biblioteca": link, "page_id": pid,
                   "anuncios_ativos": anuncios, "variacao": 0, "primeira_verificacao": data, "ultima_verificacao": data,
                   "monitoramento": False, "palavras_chave": palavras, "historico": [f"{data} · {anuncios}"]}
        p.write_text(preencher(modelo(v, MODELO_PAGINA, PAGINA_PADRAO), p.stem, valores,
                               {"pasta": pasta.relative_to(v).as_posix()}), encoding="utf-8")
        return "nova", p, None
    props, corpo = ler_fm(p.read_text(encoding="utf-8"))
    hist = [h for h in (props.get("historico") or []) if not str(h).startswith(data)]
    anterior = next((int(str(h).split("·")[-1]) for h in reversed(hist) if "·" in str(h) and str(h).split("·")[-1].strip().isdigit()), None)
    hist.append(f"{data} · {anuncios}")
    props.update(anuncios_ativos=anuncios, ultima_verificacao=data, historico=hist,
                 variacao=(anuncios - anterior) if anterior is not None else 0)
    if link and not props.get("link_biblioteca"):
        props["link_biblioteca"], props["page_id"] = link, pid
    atuais = list(props.get("palavras_chave") or [])
    props["palavras_chave"] = atuais + [x for x in palavras if x not in atuais]
    p.write_text(fm_texto(props) + corpo, encoding="utf-8")
    return "atualizada", p, anterior


def gravar_busca(v, busca):
    """Grava as bibliotecas que passaram nos filtros (e as monitoradas) e o relatório do dia."""
    if not v or not v.is_dir():
        raise ErroSpy("Nenhum cofre configurado. Escolha o cofre em Configurações.")
    spy = pasta_spy(v)
    nicho = limpar(busca.get("nicho") or "Geral")
    data = datetime.date.today().isoformat()
    bl = blacklist(spy)
    escolhidas = [r for r in busca["resultados"] if (r.get("confere") is True or r.get("monitorada")) and r.get("anuncios") is not None]
    linhas, novas, ignoradas, total, notas = [], 0, [], 0, []
    for r in sorted(escolhidas, key=lambda x: -int(x.get("anuncios") or 0)):
        if na_blacklist(bl, r["pagina"], r.get("link"), r.get("page_id")):
            ignoradas.append(r["pagina"])
            continue
        st, p, ant = registrar(v, spy, nicho, r, data)
        novas += st == "nova"
        total += int(r.get("anuncios") or 0)
        pr, _ = ler_fm(p.read_text(encoding="utf-8"))
        var = "nova" if st == "nova" else (f"{int(r['anuncios']) - ant:+d}" if ant is not None else "—")
        pal = ", ".join(r.get("palavras") or []) or ("monitorada" if r.get("monitorada") else "—")
        linhas.append(f"| [[{p.stem}]] | {r.get('anuncios', 0)} | {var} | {'sim' if pr.get('monitoramento') else 'não'} | "
                      f"{pal} | {('[abrir](' + r['link'] + ')') if r.get('link') else '—'} |")
        notas.append({"pagina": r["pagina"], "situacao": st, "caminho": p.relative_to(v).as_posix()})
    palavras = busca["consulta"]["palavras"]
    rel = spy / "Relatórios"
    rel.mkdir(parents=True, exist_ok=True)
    nome = f"Spy {data} {nicho}"
    destino, i = rel / f"{nome}.md", 2
    while destino.exists() and busca.get("relatorio") != destino.relative_to(v).as_posix():
        destino = rel / f"{nome} ({i}).md"; i += 1
    valores = {"tipo": "spy_relatorio", "data": data, "nicho": nicho, "palavras_buscadas": palavras,
               "bibliotecas_encontradas": len(linhas), "novas": novas, "anuncios_total": total,
               "ignoradas_blacklist": len(ignoradas)}
    texto = preencher(modelo(v, MODELO_RELATORIO, RELATORIO_PADRAO), destino.stem, valores)
    resumo = (f"Palavras buscadas: {', '.join(palavras) or '—'}. País: {busca['consulta']['pais']}. "
              f"{len(linhas)} bibliotecas, {novas} novas, {total} anúncios ativos somados."
              + (f" Ignoradas pela blacklist: {', '.join(ignoradas)}." if ignoradas else ""))
    # o resumo entra logo depois do título; as linhas, logo abaixo do cabeçalho da tabela do modelo
    texto = re.sub(r"(^# .+\n)", lambda m: m.group(1) + "\n" + resumo + "\n", texto, count=1, flags=re.M)
    texto = re.sub(r"(^\|[^\n]*\|\n\|[-| :]+\|\n)", lambda m: m.group(1) + "".join(l + "\n" for l in linhas), texto, count=1, flags=re.M)
    destino.write_text(texto, encoding="utf-8")
    return {"relatorio": destino.relative_to(v).as_posix(), "obsidian": link_obsidian(v, destino),
            "bibliotecas": len(linhas), "novas": novas, "ignoradas": ignoradas, "notas": notas}


def por_na_blacklist(v, pagina, link, motivo):
    spy = pasta_spy(v)
    pid = page_id(link)
    with open(spy / "Blacklist.md", "a", encoding="utf-8") as f:
        f.write(f"| {limpar(pagina)} | {pid or '—'} | {(motivo or '—').replace('|', '/')} | {datetime.date.today().isoformat()} |\n")


def lista_blacklist(v):
    """As páginas da blacklist, na ordem em que entraram: [{pagina, page_id, motivo, desde}]."""
    p = pasta_spy(v) / "Blacklist.md"
    out = []
    for l in (p.read_text(encoding="utf-8").splitlines() if p.exists() else []):
        c = [x.strip() for x in l.strip().strip("|").split("|")] if l.strip().startswith("|") else []
        if len(c) >= 2 and c[0] not in ("Página", "") and not c[0].startswith("---"):
            out.append({"pagina": c[0], "page_id": "" if c[1] in ("—", "-") else c[1], "motivo": "" if len(c) < 3 or c[2] in ("—", "-") else c[2], "desde": c[3] if len(c) > 3 else ""})
    return out


def tirar_da_blacklist(v, pagina, pid=""):
    """Tira uma página da blacklist: ela volta a aparecer nas buscas. Devolve quantas linhas saíram."""
    p = pasta_spy(v) / "Blacklist.md"
    if not p.exists():
        return 0
    fica, saiu = [], 0
    for l in p.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in l.strip().strip("|").split("|")] if l.strip().startswith("|") else []
        if len(c) >= 2 and c[0].lower() == str(pagina).strip().lower() and (not pid or c[1] == pid) and c[0] != "Página":
            saiu += 1
            continue
        fica.append(l)
    if saiu:
        p.write_text("\n".join(fica) + "\n", encoding="utf-8")
    return saiu


def bibliotecas(v):
    out = []
    for p, pr in paginas(v) or []:
        out.append({"caminho": p.relative_to(v).as_posix(), "obsidian": link_obsidian(v, p), "pagina": pr.get("pagina") or p.stem,
                    "nicho": pr.get("nicho") or "", "link": pr.get("link_biblioteca") or "", "anuncios": pr.get("anuncios_ativos"),
                    "variacao": pr.get("variacao") or 0, "monitorada": bool(pr.get("monitoramento")),
                    "primeira": pr.get("primeira_verificacao") or "", "ultima": pr.get("ultima_verificacao") or "",
                    "historico": [str(h) for h in pr.get("historico") or []], "palavras": pr.get("palavras_chave") or []})
    return sorted(out, key=lambda x: -(x["anuncios"] or 0))


def monitorar(v, caminho, valor):
    p = (v / caminho).resolve()
    if v not in p.parents or p.suffix != ".md" or not p.is_file():
        raise ErroSpy("nota não encontrada no cofre")
    props, corpo = ler_fm(p.read_text(encoding="utf-8"))
    if props.get("tipo") != "spy_pagina":
        raise ErroSpy("essa nota não é uma biblioteca do Spy")
    props["monitoramento"] = bool(valor)
    p.write_text(fm_texto(props) + corpo, encoding="utf-8")


def editar(v, caminho, nome, nicho):
    """Troca o nome da página e/ou o nicho: move a pasta da biblioteca, renomeia a nota e acerta os links do Spy."""
    p = (v / caminho).resolve()
    if v not in p.parents or p.suffix != ".md" or not p.is_file():
        raise ErroSpy("nota não encontrada no cofre")
    props, corpo = ler_fm(p.read_text(encoding="utf-8"))
    if props.get("tipo") != "spy_pagina":
        raise ErroSpy("essa nota não é uma biblioteca do Spy")
    nome, nicho = limpar(nome), limpar(nicho)
    if not str(nome).strip() or nome == "Sem nome" or nicho == "Sem nome":
        raise ErroSpy("Preencha o nome da página e o nicho.")
    spy = pasta_spy(v)
    velha, nova = p.parent, spy / nicho / f"{nome} (Spy)"
    if nova.resolve() != velha.resolve() and nova.exists():
        raise ErroSpy("Já existe uma biblioteca com esse nome nesse nicho.")
    antigo_rel, antigo_link = velha.relative_to(v).as_posix(), p.stem
    props["pagina"], props["nicho"] = nome, nicho
    if nova.resolve() != velha.resolve():
        nova.parent.mkdir(parents=True, exist_ok=True)
        velha.rename(nova)
        try:
            velha.parent.rmdir()             # pasta do nicho antigo ficou vazia
        except OSError:
            pass
    alvo = nova / f"{nome} (Spy).md"
    (nova / p.name).rename(alvo) if (nova / p.name) != alvo else None
    corpo = corpo.replace(antigo_rel, nova.relative_to(v).as_posix())
    if corpo.lstrip().startswith("# "):
        corpo = re.sub(r"^(\s*)# .*$", lambda m: m.group(1) + "# " + alvo.stem, corpo, count=1, flags=re.M)
    alvo.write_text(fm_texto(props) + corpo, encoding="utf-8")
    # links [[Página (Spy)]] nos relatórios e no resto do Spy
    if antigo_link != alvo.stem:
        for n in spy.rglob("*.md"):
            t = n.read_text(encoding="utf-8")
            t2 = t.replace(f"[[{antigo_link}]]", f"[[{alvo.stem}]]").replace(f"[[{antigo_link}|", f"[[{alvo.stem}|")
            if t2 != t:
                n.write_text(t2, encoding="utf-8")
    return alvo.relative_to(v).as_posix()


def monitoradas(v, nicho=None):
    return [{"pagina": b["pagina"], "link": b["link"]} for b in bibliotecas(v)
            if b["monitorada"] and b["link"] and (not nicho or b["nicho"].lower() == nicho.lower())]


def palavras_chave(v):
    """Biblioteca/Palavras-chave Spy.md → [{secao, linhas:[[pt, en, latam]]}]."""
    p = v / PALAVRAS if v else None
    if not p or not p.is_file():
        return []
    secoes, atual = [], None
    for l in p.read_text(encoding="utf-8").splitlines():
        if l.startswith("## "):
            atual = {"secao": l[3:].strip(), "linhas": []}
            secoes.append(atual)
            continue
        m = re.match(r"^\|(.+)\|\s*$", l)
        if atual and m:
            cel = [c.strip() for c in m.group(1).split("|")]
            if cel[0] in ("Português", "") or set(cel[0]) <= set("-: "):
                continue
            atual["linhas"].append((cel + ["", "", ""])[:3])
    return [s for s in secoes if s["linhas"]]


# ---------------- as buscas (uma de cada vez: o perfil do navegador é um só) ----------------
class Spy:
    def __init__(self):
        self.lock = threading.RLock()
        self.buscas = {}
        self.proc = None          # processo do coletor em uso (busca ou navegador aberto)
        self.rodando = None       # id da busca em andamento
        self.navegador = False    # navegador visível aberto sem busca
        self.cofres = {}          # busca -> cofre em que ela foi feita (para atualizar as monitoradas no fim)
        self.atual = {"status": "parado", "total": 0, "feitas": 0, "pagina": "", "erros": [], "mudou": 0}      # o botão Atualizar das bibliotecas
        BUSCAS.mkdir(parents=True, exist_ok=True)
        for f in BUSCAS.glob("*.json"):
            try:
                b = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if b.get("status") in ("preparando", "buscando", "precisa"):
                b["status"], b["mensagem"] = "interrompida", "O Octopus IA foi fechado durante a busca."
            self.buscas[b["id"]] = b

    # --- infraestrutura
    def node(self):
        return shutil.which("node") or next((p for p in ("/usr/local/bin/node", "/opt/homebrew/bin/node") if Path(p).exists()), None)

    def instalado(self):
        nav = PASTA / "browsers"
        ok_nav = nav.is_dir() and any((d / "INSTALLATION_COMPLETE").exists() for d in nav.glob("chromium-*"))
        return bool(self.node()) and (RAIZ / "node_modules" / "playwright").is_dir() and ok_nav

    def _salvar(self, b):
        tmp = BUSCAS / f"{b['id']}.tmp"
        tmp.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
        tmp.replace(BUSCAS / f"{b['id']}.json")

    def _abrir_coletor(self, pedido):
        node = self.node()
        if not node:
            raise ErroSpy("O Spy precisa do Node.js instalado neste computador.")
        if not self.instalado():
            raise ErroSpy("O navegador do Spy não está instalado. Peça ao Claude Code ou ao Codex para rodar a instalação do Octopus IA de novo (python instalar.py).")
        p = subprocess.Popen([node, str(COLETOR)], cwd=str(RAIZ), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", env=env_filho(), bufsize=1)
        p.stdin.write(json.dumps(pedido, ensure_ascii=False) + "\n")
        p.stdin.flush()
        return p

    def _cmd(self, cmd):
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.stdin.write(json.dumps({"cmd": cmd}) + "\n")
                self.proc.stdin.flush()
                return True
        except (BrokenPipeError, OSError):
            pass
        return False

    def _fechar_navegador(self):
        if self.navegador and self.proc:
            self._cmd("parar")
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc, self.navegador = None, False

    # --- o que a interface vê
    def resumo(self, b):
        r = {k: b[k] for k in ("id", "status", "consulta", "nicho", "progresso", "mensagem", "criada", "atualizada", "relatorio", "obsidian") if k in b}
        r["confirmadas"] = sum(1 for x in b["resultados"] if x.get("confere") is True)
        return r

    def estado(self, v):
        with self.lock:
            lista = sorted(self.buscas.values(), key=lambda b: -b["criada"])[:12]
            return {"instalado": self.instalado(), "node": bool(self.node()), "rodando": self.rodando if self.rodando in self.buscas else None,
                    "navegador": self.navegador, "buscas": [self.resumo(b) for b in lista],
                    "palavras": palavras_chave(v) if v else []}

    def busca(self, bid, v=None):
        with self.lock:
            b = self.buscas.get(bid)
            if not b:
                raise ErroSpy("busca não encontrada")
            b = json.loads(json.dumps(b))
        # cada resultado diz se já está nas Bibliotecas do cofre (e se está monitorado)
        if v and v.is_dir():
            idx = {}
            for p, pr in paginas(v) or []:
                info = {"caminho": p.relative_to(v).as_posix(), "monitorada": bool(pr.get("monitoramento"))}
                if pr.get("page_id"):
                    idx["id:" + str(pr["page_id"])] = info
                idx["nome:" + str(pr.get("pagina") or "").lower()] = info
            for r in b["resultados"]:
                r["cofre"] = idx.get("id:" + str(r.get("page_id") or "-")) or idx.get("nome:" + limpar(r["pagina"]).lower())
        return b

    def monitorar_resultado(self, bid, rid, valor, v):
        """Monitorar no cartão da busca: grava a biblioteca no cofre (Swipe/Spy/<Nicho>/) já monitorada."""
        if not v or not v.is_dir():
            raise ErroSpy("Nenhum cofre configurado. Escolha o cofre em Configurações.")
        with self.lock:
            b = self.buscas.get(bid)
            r = next((x for x in (b or {}).get("resultados", []) if x["id"] == rid), None)
            if not r:
                raise ErroSpy("resultado não encontrado")
            r = dict(r)
            nicho = b.get("nicho") or "Geral"
        spy = pasta_spy(v)
        if valor:
            if na_blacklist(blacklist(spy), r["pagina"], r.get("link"), r.get("page_id")):
                raise ErroSpy("Esta página está na blacklist.")
            if r.get("anuncios") is None:
                raise ErroSpy("Não deu para ler os anúncios ativos desta página. Abra a biblioteca e confira antes.")
            _, p, _ = registrar(v, spy, nicho, r, datetime.date.today().isoformat())
        else:
            p = achar(v, limpar(r["pagina"]), r.get("page_id") or page_id(r.get("link")))
            if not p:
                return None
        monitorar(v, p.relative_to(v).as_posix(), valor)
        return p.relative_to(v).as_posix()

    # --- ações
    def iniciar(self, consulta, nicho, com_monitoradas, v):
        bruto = consulta.get("palavras") or []
        palavras = []
        for x in (re.split(r"[\n,;]+", bruto) if isinstance(bruto, str) else bruto):
            x = re.sub(r"\s+", " ", str(x)).strip()[:80]
            if x and x.lower() not in [p.lower() for p in palavras]:
                palavras.append(x)
        if not palavras or len(palavras) > 10:
            raise ErroSpy("Informe de uma a dez palavras-chave, separadas por linha ou vírgula.")
        pais = str(consulta.get("pais") or "BR").upper()
        if pais not in PAISES:
            raise ErroSpy("país inválido")
        def num(k, pad, lo, hi):
            try:
                return max(lo, min(hi, int(consulta.get(k, pad))))
            except (TypeError, ValueError):
                return pad
        c = {"palavras": palavras, "pais": pais, "min_anuncios": num("min_anuncios", 5, 1, 10000),
             "min_dias": num("min_dias", 7, 0, 3650), "max_bibliotecas": num("max_bibliotecas", 20, 1, 100),
             "ver_monitoradas": bool(consulta.get("ver_monitoradas"))}
        nicho = limpar(nicho or SEM_NICHO)
        # com nicho escolhido, confere as monitoradas dele; sem nicho, confere todas
        mon = monitoradas(v, None if nicho == SEM_NICHO else nicho) if (com_monitoradas and v and v.is_dir()) else []
        # caixinha desligada: as que já estão monitoradas não aparecem na busca nem contam para o limite
        pular = []
        if not c["ver_monitoradas"] and v and v.is_dir():
            for b in bibliotecas(v):
                if b["monitorada"]:
                    pid = re.search(r"view_all_page_id=(\d+)", b.get("link") or "")
                    pular.append({"pagina": b["pagina"], "page_id": pid.group(1) if pid else ""})
        with self.lock:
            if self.rodando:
                raise ErroSpy("Já tem uma busca em andamento. Espere terminar ou pare a atual.")
            self._fechar_navegador()
            agora = int(time.time() * 1000)
            b = {"id": secrets.token_hex(4), "status": "preparando", "consulta": c, "nicho": nicho,
                 "progresso": {"palavras_total": len(palavras), "palavras_feitas": 0, "conferidos": 0,
                               "monitoradas_total": len(mon), "monitoradas_feitas": 0, "atual": None},
                 "resultados": [], "mensagem": None, "criada": agora, "atualizada": agora}
            self.buscas[b["id"]] = b
            self.cofres[b["id"]] = v
            self.proc = self._abrir_coletor({"acao": "buscar", "consulta": c, "monitoradas": mon, "pular": pular})
            self.rodando = b["id"]
            self._salvar(b)
        threading.Thread(target=self._ler, args=(b["id"], self.proc), daemon=True).start()
        return self.busca(b["id"])

    def _ler(self, bid, proc):
        erro = None
        for linha in proc.stdout:
            try:
                ev = json.loads(linha)
            except ValueError:
                continue
            with self.lock:
                b = self.buscas[bid]
                t = ev.get("tipo")
                if t == "progresso":
                    b["progresso"].update({k: v for k, v in ev.items() if k != "tipo"})
                    if b["status"] in ("preparando", "precisa"):
                        b["status"], b["mensagem"] = "buscando", None
                elif t == "resultado":
                    r = ev["r"]
                    i = next((k for k, x in enumerate(b["resultados"]) if x["id"] == r["id"]), None)
                    if i is None:
                        b["resultados"].append(r)
                    else:
                        b["resultados"][i] = r
                    if b["status"] == "preparando":
                        b["status"] = "buscando"
                elif t == "acao":
                    b["status"], b["mensagem"] = "precisa", ev.get("mensagem")
                elif t == "erro":
                    erro = ev.get("mensagem")
                elif t == "fim" and ev.get("parado"):
                    b["status"] = "parada"
                b["atualizada"] = int(time.time() * 1000)
                self._salvar(b)
        proc.wait()
        with self.lock:
            b = self.buscas[bid]
            if b["status"] not in ("parada",):
                b["status"] = "falhou" if erro else "concluida"
            if b["status"] == "parada":
                b["mensagem"] = "Busca parada. O que já foi achado está abaixo."
            elif erro:
                b["mensagem"] = erro
            else:
                b["mensagem"] = None
            b["progresso"]["atual"] = None
            # as monitoradas que a busca conferiu atualizam sozinhas no cofre (anúncios ativos, variação, histórico)
            v = self.cofres.pop(bid, None)
            if v and v.is_dir():
                try:
                    spy, hoje = pasta_spy(v), datetime.date.today().isoformat()
                    for r in b["resultados"]:
                        if r.get("monitorada") and r.get("anuncios") is not None:
                            registrar(v, spy, b.get("nicho") or "Geral", r, hoje)
                except OSError:
                    pass
            b["atualizada"] = int(time.time() * 1000)
            self._salvar(b)
            if self.rodando == bid:
                self.rodando, self.proc = None, None

    def parar(self, bid):
        with self.lock:
            if self.rodando != bid:
                return self.busca(bid)
            self.buscas[bid]["mensagem"] = "Parando…"
            self.buscas[bid]["status"] = "parada"
            self._cmd("parar")
        return self.busca(bid)

    def continuar(self, bid):
        with self.lock:
            if self.rodando == bid:
                self.buscas[bid]["status"], self.buscas[bid]["mensagem"] = "buscando", "Tentando de novo…"
                self._cmd("continuar")
        return self.busca(bid)

    def abrir_navegador(self, url=None):
        with self.lock:
            if self.rodando:
                self._cmd("navegador")          # durante a busca: mostra a página em que a Meta travou
                return {"ok": True}
            if self.navegador and self.proc and self.proc.poll() is None:
                if not url:
                    return {"ok": True}
                self._fechar_navegador()        # reabre já na página pedida
            self.proc = self._abrir_coletor({"acao": "abrir", **({"url": url} if url else {})})
            self.navegador = True
            proc = self.proc
        def vigiar():
            proc.wait()
            with self.lock:
                if self.proc is proc:
                    self.proc, self.navegador = None, False
        threading.Thread(target=vigiar, daemon=True).start()
        return {"ok": True}

    def _verificar(self, link, limite=150):
        """Abre uma biblioteca no coletor e devolve o que ele leu (página, anúncios ativos…). Quem chama cuida de self.rodando."""
        proc = self._abrir_coletor({"acao": "verificar", "link": link, "pais": "BR"})
        r, erro = None, None
        try:
            fim = time.time() + limite
            for linha in proc.stdout:
                try:
                    ev = json.loads(linha)
                except ValueError:
                    continue
                if ev.get("tipo") == "verificado":
                    r = ev["r"]
                elif ev.get("tipo") == "erro":
                    erro = ev.get("mensagem")
                if time.time() > fim:
                    erro = erro or "A Meta demorou demais para responder."
                    break
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        if not r or r.get("anuncios") is None:
            raise ErroSpy(erro or "Não deu para ler quantos anúncios ativos essa biblioteca tem.")
        return r

    def atualizacao(self):
        with self.lock:
            return dict(self.atual, erros=list(self.atual["erros"]))

    def atualizar_monitoradas(self, v, nicho=None):
        """Botão Atualizar: abre o link de cada biblioteca monitorada, lê os anúncios ativos e grava no histórico do dia."""
        if not v or not v.is_dir():
            raise ErroSpy("Nenhum cofre configurado. Escolha o cofre em Configurações.")
        alvo = [b for b in bibliotecas(v) if b["monitorada"] and b["link"] and (not nicho or b["nicho"].lower() == str(nicho).lower())]
        if not alvo:
            raise ErroSpy("Nenhuma biblioteca monitorada" + (f" em {nicho}" if nicho else "") + ". Ligue o Monitorar nas que você quer acompanhar.")
        with self.lock:
            if self.rodando:
                raise ErroSpy("O Spy já está ocupado (uma busca ou outra atualização). Espere terminar.")
            self._fechar_navegador()
            self.rodando = "atualizar"
            self.atual = {"status": "rodando", "total": len(alvo), "feitas": 0, "pagina": alvo[0]["pagina"], "erros": [], "mudou": 0, "inicio": time.time()}

        def rodar():
            spy, hoje = pasta_spy(v), datetime.date.today().isoformat()
            try:
                for b in alvo:
                    with self.lock:
                        if self.atual["status"] != "rodando":
                            break
                        self.atual["pagina"] = b["pagina"]
                    try:
                        r = self._verificar(b["link"], 120)
                        _, _, antes = registrar(v, spy, b["nicho"], {**r, "pagina": b["pagina"], "link": b["link"], "palavras": []}, hoje)
                        if antes is not None and antes != int(r.get("anuncios") or 0):
                            with self.lock:
                                self.atual["mudou"] += 1
                    except (ErroSpy, OSError) as e:
                        with self.lock:
                            self.atual["erros"].append(f"{b['pagina']}: {e}")
                    with self.lock:
                        self.atual["feitas"] += 1
            finally:
                with self.lock:
                    self.rodando = None
                    self.atual["status"] = "pronto" if self.atual["status"] == "rodando" else "parado"
                    self.atual["pagina"] = ""
        threading.Thread(target=rodar, daemon=True).start()
        return self.atualizacao()

    def parar_atualizacao(self):
        with self.lock:
            if self.atual["status"] == "rodando":
                self.atual["status"] = "parando"
        return self.atualizacao()

    def adicionar(self, link, nicho, v):
        """Adicionar biblioteca à mão: só o link e o nicho; o coletor confere página, anúncios ativos e o resto."""
        if not v or not v.is_dir():
            raise ErroSpy("Nenhum cofre configurado. Escolha o cofre em Configurações.")
        link = str(link or "").strip()
        u = urllib.parse.urlparse(link)
        if u.scheme != "https" or not re.fullmatch(r"(www\.|m\.)?facebook\.com", u.netloc) or not u.path.startswith("/ads/library"):
            raise ErroSpy("Cole o link da Biblioteca de Anúncios (facebook.com/ads/library/...).")
        nicho = limpar(nicho or "")
        if nicho == "Sem nome":
            raise ErroSpy("Diga o nicho.")
        with self.lock:
            if self.rodando:
                raise ErroSpy("Tem uma busca em andamento. Espere terminar para adicionar.")
            self._fechar_navegador()
            proc = self._abrir_coletor({"acao": "verificar", "link": link, "pais": "BR"})
            self.rodando = "adicionar"
        r, erro = None, None
        try:
            fim = time.time() + 150
            for linha in proc.stdout:
                try:
                    ev = json.loads(linha)
                except ValueError:
                    continue
                if ev.get("tipo") == "verificado":
                    r = ev["r"]
                elif ev.get("tipo") == "erro":
                    erro = ev.get("mensagem")
                if time.time() > fim:
                    erro = erro or "A Meta demorou demais para responder."
                    break
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        finally:
            with self.lock:
                self.rodando = None
        if not r:
            raise ErroSpy(erro or "Não deu para ler essa biblioteca.")
        spy = pasta_spy(v)
        if na_blacklist(blacklist(spy), r["pagina"], r.get("link"), r.get("page_id")):
            raise ErroSpy(f"{r['pagina']} está na blacklist.")
        if r.get("anuncios") is None:
            raise ErroSpy("Abri a biblioteca, mas não consegui ler quantos anúncios ativos ela tem.")
        _, p, _ = registrar(v, spy, nicho, {**r, "palavras": []}, datetime.date.today().isoformat())
        monitorar(v, p.relative_to(v).as_posix(), True)
        return {"caminho": p.relative_to(v).as_posix(), "pagina": r["pagina"], "anuncios": r["anuncios"]}

    def gravar(self, bid, v):
        with self.lock:
            b = self.buscas.get(bid)
            if not b:
                raise ErroSpy("busca não encontrada")
            if self.rodando == bid:
                raise ErroSpy("Espere a busca terminar para gravar.")
            info = gravar_busca(v, b)
            b["relatorio"], b["obsidian"] = info["relatorio"], info["obsidian"]
            self._salvar(b)
            return info

    def apagar(self, bid):
        with self.lock:
            if self.rodando == bid:
                raise ErroSpy("Pare a busca antes de apagar.")
            self.buscas.pop(bid, None)
            (BUSCAS / f"{bid}.json").unlink(missing_ok=True)
