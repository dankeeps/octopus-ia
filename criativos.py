"""Gravação dos documentos da aba Criativos no cofre.

O agente entrega um documento só (tipo: anuncios ou tipo: big-ideas). Aqui ele é separado e cada
item vira uma nota, encaixada no modelo do cofre (Biblioteca/Modelos/Anúncio.md e Big idea.md):

    Projetos/{Expert}/{Oferta}/Anúncios/AD 07 - <título>.md
    Projetos/{Expert}/{Oferta}/Big ideas/<nome>.md

Big idea, narrativa e formato entram como [[links]], para os painéis das notas da biblioteca
("Anúncios com esta narrativa", "…neste formato", "…com esta big idea") funcionarem no Cérebro.
"""
import datetime, re
from pathlib import Path

import agentes
from spy import fm_texto, ler_fm, limpar, link_obsidian

MODELO_ANUNCIO = "Biblioteca/Modelos/Anúncio.md"
MODELO_BIG_IDEA = "Biblioteca/Modelos/Big idea.md"
ANUNCIO_PADRAO = """---
tipo: anuncio
id: ""
expert: ""
oferta: ""
vsl: ""
big_idea: ""
narrativa: []
formato: []
angulo: []
persona: ""
tipo_hook: ""
hook: ""
palavras:
tempo: ""
status: "para gravação"
metodo_de_copy: "Octopus - "
data: "{{date}}"
---
# {{title}}

## Roteiro
"""
# os números de cada anúncio, nas duas divisões do modelo (ic = custo por início de checkout)
METRICAS_TRAFEGO = ["gasto", "faturamento", "hook_rate", "hold_rate", "ic", "ctr", "cpa", "cpm", "conversao_checkout"]
METRICAS_VSL = ["play_rate", "retencao_1min", "retencao_pitch", "conversao"]
METRICAS_ANUNCIO = METRICAS_TRAFEGO + METRICAS_VSL
# as fases de um anúncio, na ordem em que ele anda
STATUS_ANUNCIO = ["para gravação", "gravado", "para edição", "editado", "no ar", "validou", "não validou"]
BIG_IDEA_PADRAO = """---
tipo: big_idea
big_idea: ""
oferta: ""
origem: ""
criada: "{{date}}"
---
# {{title}}

## Anúncios com esta big idea

| Anúncio | Formato |
|---|---|
"""


class ErroCriativos(Exception):
    pass


def _modelo(v, rel, padrao):
    p = v / rel
    return p.read_text(encoding="utf-8") if p.is_file() else padrao


def _itens(doc, rotulo):
    """Divide o documento nas seções "## <rotulo> N: título"."""
    _, corpo = ler_fm(doc)
    out = []
    for bloco in re.split(rf"^## {rotulo}[ \t]*\d*[ \t]*(?:[:—–-][ \t]*)?", corpo, flags=re.M)[1:]:      # o título depois do número é opcional
        titulo, _, resto = bloco.partition("\n")
        out.append((titulo.strip(), resto))
    return out


def _campo(texto, nome):
    m = re.search(rf"\*\*{re.escape(nome)}:\*\*[ \t]*(.+?)(?=[ \t]*·[ \t]*\*\*|\n|$)", texto)
    return m.group(1).strip() if m else ""


def _secao(texto, nome):
    m = re.search(rf"^### {re.escape(nome)}\s*\n(.*?)(?=^### |^## |\Z)", texto, re.S | re.M)
    return m.group(1).strip() if m else ""


def _preencher(modelo, titulo, valores, secoes=None):
    """Propriedades na ordem do modelo; corpo do modelo, com o texto de cada seção logo abaixo do título dela."""
    props, corpo = ler_fm(modelo)
    hoje = datetime.date.today().isoformat()
    for k in list(props):                       # {{date}} que sobrou no modelo
        if props[k] == "{{date}}":
            props[k] = hoje
    props.update(valores)
    corpo = corpo.replace("{{title}}", titulo).replace("{{date}}", hoje)
    for nome, txt in (secoes or {}).items():
        if not txt:
            continue
        if re.search(rf"^## {re.escape(nome)}[ \t]*$", corpo, re.M):
            corpo = re.sub(rf"^## {re.escape(nome)}[ \t]*\n*", lambda m: f"## {nome}\n\n{txt}\n\n", corpo, count=1, flags=re.M)
        else:
            corpo = corpo.rstrip("\n") + f"\n\n## {nome}\n\n{txt}\n"
    return fm_texto(props) + corpo


def _link(cofre, pasta, tipo, nome):
    """Nome do catálogo → [[nota]] (se a nota existir na biblioteca; senão, o texto como veio)."""
    nome = re.sub(r"^\[\[|\]\]$", "", str(nome or "").strip())
    if not nome:
        return None
    achou = agentes._achar_nota(agentes._notas(cofre, pasta, tipo), nome)
    return f"[[{achou[0].stem}]]" if achou else nome


def _lista_links(cofre, pasta, tipo, texto):
    return [x for x in (_link(cofre, pasta, tipo, p) for p in re.split(r"\s*(?:,|;| \+ | e (?=\d))\s*", texto or "") if p.strip()) if x]


def _big_idea(v, base, tese, oferta, origem="", nome=None):
    """Acha a nota da big idea pela frase dela (ou cria). Devolve (caminho, criada?)."""
    pasta = base / "Big ideas"
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = re.sub(r"\W+", " ", tese.lower()).strip()
    for p in pasta.glob("*.md"):
        pr, _ = ler_fm(p.read_text(encoding="utf-8"))
        if pr.get("tipo") == "big_idea" and re.sub(r"\W+", " ", str(pr.get("big_idea") or pr.get("tese") or "").lower()).strip() == alvo:
            return p, False
    titulo = limpar(nome or tese)[:70].rstrip(" .,")
    arq, i = pasta / f"{titulo}.md", 2
    while arq.exists():
        arq = pasta / f"{titulo} ({i}).md"; i += 1
    arq.write_text(_preencher(_modelo(v, MODELO_BIG_IDEA, BIG_IDEA_PADRAO), arq.stem,
                              {"tipo": "big_idea", "big_idea": tese, "oferta": oferta, "origem": origem}), encoding="utf-8")
    return arq, True


def _vincular_anuncio(bi, anuncio, formatos):
    """Acrescenta o anúncio (e os formatos dele) na tabela "Anúncios com esta big idea" da nota da big idea."""
    t = bi.read_text(encoding="utf-8")
    if f"[[{anuncio}]]" in t:
        return
    linha = f"| [[{anuncio}]] | {', '.join(str(f) for f in formatos) or '(sem formato)'} |"
    if not re.search(r"^## Anúncios com esta big idea", t, re.M):
        t = t.rstrip("\n") + "\n\n## Anúncios com esta big idea\n\n| Anúncio | Formato |\n|---|---|\n"
    cab = re.search(r"^## Anúncios com esta big idea[^\n]*\n", t, re.M)
    resto = t[cab.end():]
    fim = re.search(r"^## ", resto, re.M)
    secao, depois = (resto[:fim.start()], resto[fim.start():]) if fim else (resto, "")
    if "|---" not in secao:                                   # nota antiga, sem a tabela
        secao = "\n| Anúncio | Formato |\n|---|---|\n"
    bi.write_text(t[:cab.end()] + secao.rstrip("\n") + "\n" + linha + "\n" + ("\n" + depois if depois else ""), encoding="utf-8")


def paragrafos(roteiro):
    """Roteiro sempre em parágrafos: uma linha em branco entre as falas. A marcação ([Expert], [Texto na tela: …]) fica colada na fala que vem depois dela."""
    out, cola = [], False
    for l in (x.strip() for x in str(roteiro or "").splitlines()):
        if not l:
            cola = False
            continue
        if cola:
            out[-1] += "\n" + l
        else:
            out.append(l)
        cola = bool(re.fullmatch(r"\[[^\]]*\]", l))
    return "\n\n".join(out)


def remessas(pasta):
    """Números das remessas que já existem em Anúncios/ (pastas "Remessa NN")."""
    return sorted(int(m.group(1)) for p in (pasta.iterdir() if pasta.is_dir() else []) if p.is_dir() for m in [re.fullmatch(r"Remessa (\d+)", p.name)] if m)


def situacao_anuncios(v, expert, oferta):
    """O que a oferta já tem de anúncio: último número, próximo, e quantos em cada remessa."""
    pasta = v / "Projetos" / expert / oferta / "Anúncios"
    nums = [int(m.group(1)) for p in (pasta.rglob("AD *.md") if pasta.is_dir() else []) for m in [re.match(r"AD (\d+)", p.stem)] if m]
    return {"total": len(nums), "ultimo": max(nums or [0]), "proximo": max(nums or [0]) + 1,
            "remessas": [{"remessa": r, "anuncios": len(list((pasta / f"Remessa {r:02d}").glob("AD *.md")))} for r in remessas(pasta)]}


def gravar(v, tipo, expert, oferta, doc, passo=lambda t: None, remessa="nova"):
    """tipo: "anuncio" | "bigidea". Devolve {caminho, obsidian, notas:[…]}."""
    base = v / "Projetos" / expert / oferta
    base.mkdir(parents=True, exist_ok=True)
    notas = []
    if tipo == "bigidea":
        itens = _itens(doc, "Big idea")
        if not itens:
            raise ErroCriativos('Não achei nenhuma seção "## Big idea N: …" no documento.')
        passo(f"Separando {len(itens)} big idea{'s' if len(itens) > 1 else ''}")
        for nome, txt in itens:
            tese = _campo(txt, "Big idea") or _campo(txt, "Tese") or nome
            p, nova = _big_idea(v, base, tese, oferta, " · ".join(x for x in (_campo(txt, "Origem"), _campo(txt, "Fonte")) if x), nome)
            notas.append({"caminho": p.relative_to(v).as_posix(), "nova": nova})
        primeira = v / notas[0]["caminho"]
        return {"caminho": (base / "Big ideas").relative_to(v).as_posix() + "/", "obsidian": link_obsidian(v, primeira), "notas": notas}

    itens = _itens(doc, "Anúncio")
    if not itens:
        raise ErroCriativos('Não achei nenhuma seção "## Anúncio N: …" no documento.')
    passo(f"Separando {len(itens)} anúncio{'s' if len(itens) > 1 else ''}")
    raiz = base / "Anúncios"
    raiz.mkdir(parents=True, exist_ok=True)
    # a numeração é da oferta inteira (continua de uma remessa para a outra); cada leva salva entra numa remessa
    num = max([int(m.group(1)) for p in raiz.rglob("AD *.md") for m in [re.match(r"AD (\d+)", p.stem)] if m] or [0])
    rems = remessas(raiz)
    rem = int(remessa) if str(remessa).isdigit() and int(remessa) > 0 else rems[-1] if rems and remessa == "ultima" else (rems[-1] + 1 if rems else 1)
    pasta = raiz / f"Remessa {rem:02d}"
    pasta.mkdir(parents=True, exist_ok=True)
    passo(f"Remessa {rem:02d}, a partir do AD {num + 1:02d}")
    modelo = _modelo(v, MODELO_ANUNCIO, ANUNCIO_PADRAO)
    passo("Encaixando no modelo Biblioteca/Modelos/Anúncio.md")
    # o número que o anúncio já tem no documento é mantido quando está livre e à frente da contagem (o chat numera em sequência,
    # mesmo sem salvar tudo): assim o AD salvo tem o mesmo número com que foi escrito. Número repetido ou atrasado vira o próximo livre
    usados = {int(m.group(1)) for p in raiz.rglob("AD *.md") for m in [re.match(r"AD (\d+)", p.stem)] if m}
    nums_doc = [int(x) for x in re.findall(r"^## Anúncio[ \t]*(\d+)", ler_fm(doc)[1], flags=re.M)]
    for k, (titulo, txt) in enumerate(itens):
        roteiro = paragrafos(_secao(txt, "Roteiro"))
        pedido = nums_doc[k] if len(nums_doc) == len(itens) else 0
        num = pedido if pedido > 0 and pedido not in usados else max(usados or [0]) + 1
        usados.add(num)
        if not roteiro:
            raise ErroCriativos(f'O anúncio {num} veio sem a seção Roteiro.')
        tese = _campo(txt, "Big idea")
        bi = _big_idea(v, base, tese, oferta, f"criada com o anúncio AD{num:02d}" + (": " + _campo(txt, "Método de copy") if _campo(txt, "Método de copy") else ""))[0] if tese else None
        palavras = re.search(r"\d+", _campo(txt, "Palavras"))
        valores = {"tipo": "anuncio", "id": f"AD{num:02d}", "remessa": rem, "expert": expert, "oferta": oferta,
                   "big_idea": f"[[{bi.stem}]]" if bi else "",
                   "narrativa": _lista_links(v, "Narrativas", "narrativa", _campo(txt, "Narrativa")),
                   "formato": _lista_links(v, "Formatos", "formato", _campo(txt, "Formato")),
                   "angulo": _lista_links(v, "Ângulos", "angulo", _campo(txt, "Ângulo")),
                   "persona": (lambda x: f"[[{x}]]" if x and (base / "Personas" / f"{x}.md").is_file() else x)(limpar(_campo(txt, "Persona").lstrip("@")) if _campo(txt, "Persona") else ""),
                   "tipo_hook": _campo(txt, "Tipo de hook"), "hook": _campo(txt, "Hook"),
                   "palavras": int(palavras.group()) if palavras else len(re.sub(r"\[[^\]]*\]", " ", roteiro).split()),
                   "tempo": _tempo_estimado(_campo(txt, "Tempo")), "status": STATUS_ANUNCIO[0],
                   "vsl": _campo(txt, "VSL").upper(), "metodo_de_copy": "Octopus - " + (re.sub(r"^octopus\s*[-–—:]\s*", "", _campo(txt, "Método de copy"), flags=re.I) or "não informado")}
        arq = pasta / f"AD {num:02d}.md"                      # o nome do anúncio é só a sigla e o número
        arq.write_text(_preencher(modelo, arq.stem, valores, {"Roteiro": roteiro}), encoding="utf-8")
        if bi:
            _vincular_anuncio(bi, arq.stem, [re.sub(r"^\[\[|\]\]$", "", str(f)) for f in valores["formato"]])
        notas.append({"caminho": arq.relative_to(v).as_posix(), "nova": True})
    passo("Gravando no cofre")
    return {"caminho": pasta.relative_to(v).as_posix() + "/", "obsidian": link_obsidian(v, v / notas[0]["caminho"]), "notas": notas}


def _tempo_estimado(t):
    """Tempo antes da gravação é estimativa: leva ~ na frente. O exato entra depois, com atualizar_anuncio."""
    t = str(t or "").strip().lstrip("~≈ ").strip()
    return "~" + t if t else ""


def atualizar_anuncio(v, expert, oferta, ident, campos):
    """Muda status, tempo, palavras ou vsl de um anúncio já gravado (ident: AD07, 7 ou parte do título). Devolve o caminho."""
    pasta = v / "Projetos" / expert / oferta / "Anúncios"
    alvo = re.sub(r"\D", "", str(ident)) if re.fullmatch(r"\s*(AD)?\s*\d+\s*", str(ident), re.I) else None
    achados = [p for p in sorted(pasta.rglob("AD *.md")) if (alvo and re.match(rf"AD 0*{int(alvo)}\b", p.stem)) or (not alvo and str(ident).lower() in p.stem.lower())] if pasta.is_dir() else []
    if len(achados) != 1:
        raise ErroCriativos("anúncio não encontrado" if not achados else "mais de um anúncio com esse nome: " + ", ".join(p.stem for p in achados))
    props, corpo = ler_fm(achados[0].read_text(encoding="utf-8"))
    if campos.get("status"):
        st = str(campos["status"]).strip().lower()
        if st not in STATUS_ANUNCIO:
            raise ErroCriativos("status inválido. Use um destes: " + ", ".join(STATUS_ANUNCIO))
        props["status"] = st
    if campos.get("tempo"):
        props["tempo"] = str(campos["tempo"]).strip().lstrip("~≈ ")          # medido no vídeo gravado: exato, sem ~
    if campos.get("palavras"):
        props["palavras"] = int(campos["palavras"])
    if campos.get("vsl"):
        props["vsl"] = str(campos["vsl"]).strip().upper()
    for k in METRICAS_ANUNCIO:                                # os números da campanha, como o usuário passou
        if campos.get(k) not in (None, ""):
            props[k] = campos[k]
    achados[0].write_text(fm_texto(props) + corpo, encoding="utf-8")
    return achados[0].relative_to(v).as_posix()


def gravar_bloco(v, expert, oferta, doc, passo=lambda t: None, pode_editar=True):
    """Bloco de VSL (tipo: bloco-de-vsl) → Projetos/{Expert}/{Oferta}/VSL/Blocos/NN - <bloco>.md. Bloco reescrito substitui o anterior."""
    props, corpo = ler_fm(doc)
    bloco = limpar(props.get("bloco") or "")
    if not bloco or bloco == "Sem nome" or "## Texto" not in corpo:
        raise ErroCriativos('O documento precisa ter "bloco" no cabeçalho e a seção "## Texto".')
    try:
        ordem = int(props.get("ordem") or 0)
    except (TypeError, ValueError):
        ordem = 0
    pasta = v / "Projetos" / expert / oferta / "VSL" / "Blocos"
    pasta.mkdir(parents=True, exist_ok=True)
    passo("Gravando o bloco no cofre")
    props.update({"tipo": "bloco_de_vsl", "expert": expert, "oferta": oferta, "status": props.get("status") or "aprovado"})
    arq = pasta / (f"{ordem:02d} - {bloco}.md" if ordem else f"{bloco}.md")
    if arq.exists():                                  # o bloco anterior vai para a lixeira: nada é perdido, e trocar exige a chave de edição
        if not pode_editar:
            raise ErroCriativos(f'O bloco "{bloco}" já existe e a permissão "Editar notas" está desligada em Configurações › Permissões.')
        import armazem
        armazem.para_lixeira(v, arq)
    arq.write_text(fm_texto(props) + corpo, encoding="utf-8")
    return {"caminho": arq.relative_to(v).as_posix(), "obsidian": link_obsidian(v, arq), "notas": [{"caminho": arq.relative_to(v).as_posix(), "nova": True}]}


MODELO_VSL = """---
tipo: vsl
nome: ""
versao: ""
expert: ""
oferta: ""
nicho: ""
data: "{{date}}"
link: ""
play_rate:
retencao_1min:
retencao_pitch:
conversao:
---
# {{title}}

## Script
"""


def versao_vsl(x):
    """"1", "v1", "V 1", "VSL V1" → "V1". Vazio se não der para ler."""
    m = re.search(r"(\d+)", str(x or ""))
    return f"V{int(m.group(1))}" if m else ""


def gravar_vsl(v, expert, oferta, doc, passo=lambda t: None, pode_editar=True):
    """A VSL da oferta (tipo: vsl-da-oferta) → Projetos/{Expert}/{Oferta}/VSL/VSL V{n}.md, no modelo de VSL. Regravar a mesma versão manda a anterior para a lixeira."""
    props, corpo = ler_fm(doc)
    versao = versao_vsl(props.get("versao"))
    m = re.search(r"^## Script[ \t]*\n(.*)", corpo, re.S | re.M)
    script = m.group(1).strip() if m else ""
    if not versao:
        raise ErroCriativos('Faltou a versão da VSL no cabeçalho (ex.: versao: "V1").')
    if not script:                                   # veio sem o título "## Script": o script é tudo o que está depois do título da nota
        script = re.sub(r"\A\s*# [^\n]*\n", "", corpo).strip()
    if len(script) < 200:
        raise ErroCriativos("O documento veio sem o script da VSL.")
    # sem a divisão em blocos a VSL é gravada do mesmo jeito (melhor guardada inteira do que perdida); os blocos entram quando o chat refizer
    pasta = v / "Projetos" / expert / oferta / "VSL"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"VSL {versao}.md"
    if arq.exists():
        if not pode_editar:
            raise ErroCriativos(f'A oferta já tem a VSL {versao} e a permissão "Editar notas" está desligada em Configurações › Permissões.')
        import armazem
        passo(f"Guardando a VSL {versao} anterior na lixeira")
        armazem.para_lixeira(v, arq)
    passo("Gravando a VSL no Cérebro")
    nome = limpar(props.get("nome") or "") or oferta
    if nome == "Sem nome":
        nome = oferta
    valores = {"nome": nome, "versao": versao, "expert": expert, "oferta": oferta, "data": ""}      # data só se o usuário informou: não vale a de hoje
    for k in ("nicho", "data", "link", "play_rate", "retencao_1min", "retencao_pitch", "conversao"):
        if props.get(k) not in (None, ""):
            valores[k] = props[k]
    arq.write_text(_preencher(_modelo(v, "Biblioteca/Modelos/VSL.md", MODELO_VSL), f"VSL {versao} · {nome}", valores, {"Script": script}), encoding="utf-8")
    rel = arq.relative_to(v).as_posix()
    return {"caminho": rel, "obsidian": link_obsidian(v, arq), "notas": [{"caminho": rel, "nova": True}]}


def gravar_dicionario(v, expert, oferta, doc, passo=lambda t: None, pode_editar=True):
    """Dicionário da oferta (tipo: dicionario-da-oferta) → Projetos/{Expert}/{Oferta}/Dicionário da oferta.md. O anterior vai para a lixeira do cofre."""
    props, corpo = ler_fm(doc)
    if "## 1. Jeito de falar" not in corpo:
        raise ErroCriativos("O documento não está no formato do modelo do Dicionário da oferta.")
    base = v / "Projetos" / expert / oferta
    base.mkdir(parents=True, exist_ok=True)
    arq = base / "Dicionário da oferta.md"
    if arq.exists():
        if not pode_editar:
            raise ErroCriativos('A oferta já tem um dicionário e a permissão "Editar notas" está desligada em Configurações › Permissões.')
        import armazem
        passo("Guardando o dicionário anterior na lixeira do cofre")
        armazem.para_lixeira(v, arq)
    passo("Gravando o dicionário no cofre")
    props.update({"tipo": "dicionario_da_oferta", "expert": expert, "oferta": oferta})
    arq.write_text(fm_texto(props) + corpo, encoding="utf-8")
    rel = arq.relative_to(v).as_posix()
    return {"caminho": rel, "obsidian": link_obsidian(v, arq), "notas": [{"caminho": rel, "nova": True}]}


def gravar_personas(v, expert, oferta, doc, passo=lambda t: None, pode_editar=True):
    """Documento tipo: personas → uma nota por persona em Projetos/{Expert}/{Oferta}/Personas/. Persona com o mesmo nome é substituída."""
    itens = _itens(doc, "Persona")
    if not itens:
        raise ErroCriativos('Não achei nenhuma seção "## Persona N: nome" no documento.')
    pasta = v / "Projetos" / expert / oferta / "Personas"
    pasta.mkdir(parents=True, exist_ok=True)
    passo(f"Separando {len(itens)} persona{'s' if len(itens) > 1 else ''}")
    notas = []
    for nome, txt in itens:
        nome = limpar(nome)[:60]
        resumo = _campo(txt, "Resumo")
        corpo = re.sub(r"^- \*\*Resumo:\*\*.*\n?", "", txt.strip(), count=1, flags=re.M).strip()
        corpo = re.sub(r"^### ", "## ", corpo, flags=re.M)
        arq = pasta / f"{nome}.md"
        nova = not arq.exists()
        if not nova:                                  # a persona anterior vai para a lixeira: nada é perdido, e trocar exige a chave de edição
            if not pode_editar:
                raise ErroCriativos(f'A persona "{nome}" já existe e a permissão "Editar notas" está desligada em Configurações › Permissões.')
            import armazem
            armazem.para_lixeira(v, arq)
        arq.write_text(fm_texto({"tipo": "persona", "expert": expert, "oferta": oferta, "nome": nome, "resumo": resumo,
                                 "criada": datetime.date.today().isoformat()}) + f"# {nome}\n\n{corpo}\n", encoding="utf-8")
        notas.append({"caminho": arq.relative_to(v).as_posix(), "nova": nova})
    passo("Gravando no cofre")
    return {"caminho": pasta.relative_to(v).as_posix() + "/", "obsidian": link_obsidian(v, v / notas[0]["caminho"]), "notas": notas}


def personas(v, expert, oferta):
    """As personas de uma oferta: nome, resumo e o texto inteiro."""
    pasta = v / "Projetos" / expert / oferta / "Personas"
    out = []
    for p in sorted(pasta.glob("*.md")) if pasta.is_dir() else []:
        props, corpo = ler_fm(p.read_text(encoding="utf-8"))
        if str(props.get("tipo") or "") != "persona":
            continue
        out.append({"nome": str(props.get("nome") or p.stem), "resumo": str(props.get("resumo") or ""), "texto": corpo.strip(),
                    "caminho": p.relative_to(v).as_posix(), "obsidian": link_obsidian(v, p), "criada": str(props.get("criada") or "")})
    return out
