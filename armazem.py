"""Armazém do Octopus IA no Cérebro (a pasta de arquivos do Octopus IA).

Tudo o que o Atlas gera para um projeto ligado fica em `Projetos/{Expert}/{Oferta}/Atlas/`:

    Projeto Atlas.md                      dados do projeto
    {Nome do flow}/Flow.md                nós e ligações do flow
    {Nome do flow}/Conversa - ….md        conversas dos nós do flow
    {Nome do flow}/Arquivos/              arquivos subidos na Inteligência em arquivo
    Chats/{Área}/Conversa - ….md          conversas fora dos flows

Cada nota tem frontmatter com `atlas_tipo` e `atlas_id`, um texto legível e, no fim,
os dados exatos num comentário `%% … %%` (o leitor de notas esconde). É desse comentário que o
Atlas reabre as coisas. Nota do Atlas que some do estado vai para a lixeira do cofre (`.trash`).
Projeto sem pasta no cofre continua em `dados/app.json` (na pasta de dados do aplicativo) até ser ligado.
"""
import json, os, re, shutil, time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
from locais import LOCAL
LOCAL_FLOWS = LOCAL / "flows"
MARCA = "atlas-dados"
AREAS = {"spy": "Spy", "vsl": "VSL", "criativos": "Criativos", "edicao": "Edição", "trafego": "Tráfego", "funil": "Funil"}
AGENTES_NOME = {"espiao": "Spy - Espião", "copy": "Criativos - Copywriter", "auditor": "Criativos - Auditor",
                "corte": "Edição - Corte bruto", "editor": "Edição - Editor", "gestor": "Tráfego - Gestor",
                "funil": "Funil - Agente de funil", "otimizacao": "Funil - Otimização",
                "biblia": "VSL - Bíblia do nicho", "briefing": "VSL - Briefing de tese"}
TIPOS_NO = {"chatgpt": "ChatGPT", "inteligencia": "Inteligência em texto", "arquivo": "Inteligência em arquivo",
            "biblia": "Bíblia do nicho", "briefing": "Briefing de tese", "chat": "Chat"}


# ---------------- nomes e datas ----------------
def nome_arquivo(t, limite=60):
    t = re.sub(r'[\\/:*?"<>|#^\[\]\n\r\t]+', " ", str(t or "")).strip().strip(".")
    t = re.sub(r"\s+", " ", t)
    from locais import nome_windows
    return (nome_windows(t[:limite].rstrip()) or "Sem nome")


def iso(ms):
    try:
        return datetime.fromtimestamp((ms or 0) / 1000).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError, TypeError):
        return ""


def ligado(v, p):
    """O projeto é ligado ao expert (todas as ofertas dele). Projetos antigos, ligados a uma oferta, continuam valendo."""
    if not (v and p.get("vinculado") and p.get("expert")):
        return False
    return (v / "Projetos" / p["expert"] / (p.get("oferta") or "")).is_dir()


def pasta_atlas(v, p):
    return v / "Projetos" / p["expert"] / (p.get("oferta") or "") / "Atlas"


def pasta_flow(v, p, f):
    return pasta_atlas(v, p) / nome_arquivo(f.get("nome") or "Flow")


# ---------------- nota ----------------
def nota(tipo, atlas_id, campos, corpo, dados):
    fm = [f"atlas_tipo: {tipo}", f"atlas_id: {atlas_id}"]
    for k, val in campos.items():
        if val is None or val == "":
            continue
        fm.append(f"{k}: {json.dumps(val, ensure_ascii=False)}")
    bloco = json.dumps(dados, ensure_ascii=False).replace("%%", "% %")
    return "---\n" + "\n".join(fm) + "\n---\n" + corpo.rstrip() + f"\n\n%%\n{MARCA}\n{bloco}\n%%\n"


def ler_nota(path):
    """(frontmatter, dados) de uma nota do Atlas; (None, None) se não for do Atlas."""
    try:
        t = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, None
    m = re.match(r"\A---\n(.*?)\n---\n", t, re.S)
    if not m or "atlas_id:" not in m.group(1):
        return None, None
    fm = {}
    for linha in m.group(1).splitlines():
        if ":" in linha:
            k, v = linha.split(":", 1)
            v = v.strip()
            try:
                fm[k.strip()] = json.loads(v)
            except ValueError:
                fm[k.strip()] = v
    d = re.search(r"%%\n" + MARCA + r"\n(.*?)\n%%\s*\Z", t, re.S)
    try:
        dados = json.loads(d.group(1)) if d else {}
    except ValueError:
        dados = {}
    return fm, dados


# ---------------- textos legíveis ----------------
def corpo_projeto(p):
    return f"# {p.get('nome','Projeto')}\n\nProjeto do Atlas ligado a esta pasta. Os flows e as conversas do Atlas ficam nas pastas ao lado."


def corpo_flow(f):
    nos = {n["id"]: n for n in f.get("nodes") or []}
    rot = lambda n: TIPOS_NO.get(n.get("type"), n.get("type", "nó"))
    linhas = [f"# {f.get('nome','Flow')}", "", f"Flow do Atlas com {len(nos)} nós.", "", "## Nós"]
    for n in nos.values():
        extra = ""
        if n.get("type") == "inteligencia" and (n.get("data") or {}).get("texto"):
            extra = ": " + n["data"]["texto"].strip().replace("\n", " ")[:120]
        if n.get("type") == "arquivo":
            arqs = [a.get("nome") for a in (n.get("data") or {}).get("arquivos") or []]
            if arqs:
                extra = ": " + ", ".join(f"[[Arquivos/{a}]]" for a in arqs)
        linhas.append(f"- {rot(n)}{extra}")
    linhas += ["", "## Ligações"]
    for e in f.get("edges") or []:
        a, b = nos.get(e.get("source")), nos.get(e.get("target"))
        if a and b:
            linhas.append(f"- {rot(a)} → {rot(b)}")
    return "\n".join(linhas)


def corpo_conversa(c):
    linhas = [f"# {c.get('titulo') or 'Conversa'}", ""]
    for m in c.get("msgs") or []:
        if m.get("r") == "user":
            anexos = ", ".join(a.get("nome", "") for a in m.get("anexos") or [])
            linhas += ["**Você:**", (m.get("t") or "").strip() + (f"\n\n_Anexos: {anexos}_" if anexos else ""), ""]
        else:
            txt = (m.get("t") or "").strip()
            if m.get("erro"):
                txt += ("\n\n" if txt else "") + f"_{m['erro']}_"
            linhas += ["**Atlas:**", txt or "_(sem texto)_", ""]
            if m.get("doc"):
                linhas += ["> [!note]- Documento gerado", "> " + m["doc"].replace("\n", "\n> "), ""]
    return "\n".join(linhas)


# ---------------- do estado para o cofre ----------------
def desejados(v, estado):
    """{atlas_id: (caminho, conteúdo, tipo)} para todos os projetos ligados."""
    out = {}
    for p in estado.get("projects") or []:
        if not ligado(v, p):
            continue
        base = pasta_atlas(v, p)
        dados_p = {k: p[k] for k in p if k not in ("flows", "convs")}
        out[p["id"]] = (base / "Projeto Atlas.md",
                        nota("projeto", p["id"], {"nome": p.get("nome"), "nicho": p.get("nicho")}, corpo_projeto(p), dados_p), "projeto")
        no_do_flow = {}
        for f in p.get("flows") or []:
            pf = pasta_flow(v, p, f)
            for n in f.get("nodes") or []:
                no_do_flow[n["id"]] = (f, pf)
            out[f["id"]] = (pf / "Flow.md", nota("flow", f["id"], {"nome": f.get("nome"), "projeto": p.get("nome"),
                            "criado": iso(f.get("criado")), "atualizado": iso(f.get("atual"))}, corpo_flow(f), f), "flow")
        for chave, conversas in (p.get("convs") or {}).items():
            for c in conversas or []:
                if not c.get("msgs"):
                    continue
                if chave in no_do_flow:
                    f, pasta = no_do_flow[chave]
                    campos = {"flow": f.get("nome"), "no": chave}
                else:
                    pasta = base / "Chats" / nome_arquivo(AGENTES_NOME.get(chave, chave))
                    campos = {"agente": chave}
                nome = f"Conversa - {nome_arquivo(c.get('titulo') or 'sem título', 40)} ({c['id']}).md"
                campos.update({"titulo": c.get("titulo"), "chave": chave, "atualizado": iso(c.get("atual"))})
                out[c["id"]] = (pasta / nome, nota("conversa", c["id"], campos, corpo_conversa(c), c), "conversa")
    return out


def indexar(v):
    """{atlas_id: (caminho, tipo)} das notas do Atlas que já existem no cofre."""
    idx = {}
    base = v / "Projetos" if v else None
    if not base or not base.is_dir():
        return idx
    for atlas in base.glob("*/*/Atlas"):
        for md in atlas.rglob("*.md"):
            fm, _ = ler_nota(md)
            if fm and fm.get("atlas_id"):
                idx[str(fm["atlas_id"])] = (md, fm.get("atlas_tipo"))
    return idx


def para_lixeira(v, alvo):
    """Move para a lixeira do Octopus IA (.trash no Cérebro): some da vista, mas dá para recuperar."""
    if not alvo.exists():
        return
    lixo = v / ".trash"
    lixo.mkdir(exist_ok=True)
    destino = lixo / alvo.name
    if destino.exists():
        destino = lixo / f"{alvo.stem} {int(time.time())}{alvo.suffix}"
    shutil.move(str(alvo), str(destino))


def gravar(path, conteudo):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.read_text(encoding="utf-8") == conteudo:
            return
    except (FileNotFoundError, UnicodeDecodeError):
        pass
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(conteudo, encoding="utf-8")
    os.replace(tmp, path)


def materializar(v, estado):
    """Deixa o cofre igual ao estado: grava o que mudou, move o que foi renomeado, manda para a lixeira o que saiu."""
    if not v or not v.is_dir():
        return
    quer = desejados(v, estado)
    tem = indexar(v)
    # 1) flows: a pasta inteira acompanha o nome do flow; flow excluído leva a pasta para a lixeira
    for fid, (caminho, tipo) in list(tem.items()):
        if tipo != "flow":
            continue
        if fid not in quer:
            para_lixeira(v, caminho.parent)
            continue
        nova = quer[fid][0].parent
        try:                                              # Mac e Windows não distinguem maiúsculas: "flow a" e "Flow A" são a MESMA pasta
            mesma = caminho.parent != nova and nova.exists() and os.path.samefile(caminho.parent, nova)
        except OSError:
            mesma = False
        if mesma:                                         # só a caixa das letras mudou: renomeia direto (jamais tratar como duas pastas)
            try:
                os.rename(caminho.parent, nova)
            except OSError:
                pass
            continue
        if caminho.parent != nova and not nova.exists():
            nova.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(caminho.parent), str(nova))
        elif caminho.parent != nova and caminho.parent.is_dir():
            # a pasta com o nome novo já existe (ex.: um arquivo foi subido antes de a mudança de nome ser gravada):
            # junta as duas em vez de deixar o flow em duas pastas. O que já está na nova fica; o resto vem da antiga
            for item in list(caminho.parent.iterdir()):
                alvo = nova / item.name
                if item.is_dir() and alvo.is_dir():
                    for arq in list(item.iterdir()):
                        if not (alvo / arq.name).exists():
                            shutil.move(str(arq), str(alvo / arq.name))
                elif not alvo.exists():
                    shutil.move(str(item), str(alvo))
            para_lixeira(v, caminho.parent)
    tem = indexar(v)
    # 2) arquivos subidos antes do projeto estar ligado: entram na pasta do flow
    for p in estado.get("projects") or []:
        if ligado(v, p):
            for f in p.get("flows") or []:
                antiga = LOCAL_FLOWS / f["id"]
                if antiga.is_dir():
                    destino = pasta_flow(v, p, f) / "Arquivos"
                    destino.mkdir(parents=True, exist_ok=True)
                    for arq in antiga.rglob("*"):
                        if arq.is_file() and not (destino / arq.name).exists():
                            shutil.move(str(arq), str(destino / arq.name))
                    shutil.rmtree(antiga, ignore_errors=True)
    # 3) notas: renomeia, grava, e manda para a lixeira o que não existe mais
    for aid, (caminho, conteudo, tipo) in quer.items():
        atual = tem.get(aid)
        if atual and atual[0] != caminho and atual[0].exists() and not caminho.exists():
            caminho.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(atual[0]), str(caminho))
        gravar(caminho, conteudo)
    for aid, (caminho, tipo) in tem.items():
        if aid not in quer and tipo != "flow" and caminho.exists():
            para_lixeira(v, caminho)
    # 4) pastas de chats que ficaram vazias
    base = v / "Projetos"
    for chats in base.glob("*/*/Atlas/Chats/*"):
        if chats.is_dir() and not any(chats.iterdir()):
            chats.rmdir()


# ---------------- do cofre para o estado ----------------
def carregar(v):
    """Projetos ligados, reconstruídos a partir das notas do cofre."""
    if not v or not (v / "Projetos").is_dir():
        return []
    projetos = []
    for atlas in sorted(list((v / "Projetos").glob("*/Atlas")) + list((v / "Projetos").glob("*/*/Atlas"))):
        fm, dados = ler_nota(atlas / "Projeto Atlas.md")
        if not fm or fm.get("atlas_tipo") != "projeto":
            continue
        p = dict(dados or {})
        p.update({"id": str(fm["atlas_id"]), **({"expert": atlas.parent.name, "oferta": ""} if atlas.parent.parent == v / "Projetos" else {"expert": atlas.parent.parent.name, "oferta": atlas.parent.name}),
                  "vinculado": True, "noCofre": True, "flows": [], "convs": {}})
        for md in atlas.rglob("*.md"):
            fmn, d = ler_nota(md)
            if not fmn or not d:
                continue
            # a mesma nota em duas pastas (sobra de uma mudança de nome): vale a mais nova, nunca as duas
            if fmn.get("atlas_tipo") == "flow":
                k = next((i for i, x in enumerate(p["flows"]) if x.get("id") == d.get("id")), -1)
                if k < 0:
                    p["flows"].append(d)
                elif (d.get("atual") or 0) > (p["flows"][k].get("atual") or 0):
                    p["flows"][k] = d
            elif fmn.get("atlas_tipo") == "conversa" and fmn.get("chave"):
                lista = p["convs"].setdefault(str(fmn["chave"]), [])
                k = next((i for i, x in enumerate(lista) if x.get("id") == d.get("id")), -1)
                if k < 0:
                    lista.append(d)
                elif (d.get("atual") or 0) > (lista[k].get("atual") or 0):
                    lista[k] = d
        projetos.append(p)
    return projetos


# ---------------- arquivos da Inteligência em arquivo ----------------
def pasta_arquivos(v, estado, fid):
    """Onde ficam os arquivos subidos num flow: na pasta do flow no cofre, ou em .local se o projeto não está ligado."""
    for p in (estado or {}).get("projects") or []:
        for f in p.get("flows") or []:
            if f.get("id") == fid and ligado(v, p):
                return pasta_flow(v, p, f) / "Arquivos"
    return LOCAL_FLOWS / fid


def arquivo_em_uso(estado, fid, nome, exceto_no=None):
    for p in (estado or {}).get("projects") or []:
        for f in p.get("flows") or []:
            if f.get("id") != fid:
                continue
            for n in f.get("nodes") or []:
                if n.get("id") == exceto_no:
                    continue
                d = n.get("data") or {}
                if any(a.get("nome") == nome for a in d.get("arquivos") or []) or \
                   any(s and s.get("origem") == "arquivo" and s.get("nome") == nome for s in d.get("slots") or []):
                    return True
    return False
