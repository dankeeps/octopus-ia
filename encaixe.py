"""Encaixe no modelo do Cérebro: vale para toda gravação de documento que tem modelo na Biblioteca.

Antes de gravar, o Codex lê o modelo que está no cofre naquele momento e reescreve o
documento na estrutura dele. Depois este módulo confere, sem IA, se o resultado tem as
mesmas chaves de frontmatter, os mesmos títulos (## e ###) na ordem e as mesmas colunas
de tabela. Se faltar algo, o Codex recebe a lista do que faltou e tenta mais uma vez.
"""
import re, unicodedata

INSTRUCOES = """Você encaixa documentos no modelo da Biblioteca do Octopus IA. Responda em português do Brasil.

Você recebe o MODELO (o arquivo do cofre, com a estrutura que manda) e o DOCUMENTO gerado por um agente.
Devolva o DOCUMENTO reescrito exatamente na estrutura do MODELO:
- Frontmatter com as mesmas chaves do modelo, na mesma ordem. Preencha com o que o documento tiver; o que não tiver fica com o valor vazio do modelo.
- Os mesmos títulos `##` e `###` do modelo, com o mesmo texto e na mesma ordem. O título `#` pode levar o nome do nicho ou da oferta depois do texto do modelo.
- Títulos `####` do modelo que são exemplo de item (como "VSL 1: página ou oferta") se repetem uma vez para cada item que o documento tiver, com o nome real no lugar.
- Toda tabela do modelo aparece com as mesmas colunas, na mesma ordem e com o mesmo cabeçalho. As linhas vêm do documento. Linha fixa do modelo (como os nomes dos blocos) continua lá, mesmo sem dado.
- Os avisos explicativos do modelo (linhas que começam com `> [!`) ficam como estão no modelo.
- O conteúdo vem só do DOCUMENTO. Não invente dado, número, nome ou citação. O que o documento não tiver fica vazio como no modelo.
- Conteúdo do documento que não cabe em nenhuma seção do modelo vai para a seção mais próxima, sem se perder.

Responda só com o Markdown final, começando pela linha `---`, sem cercas de código e sem comentário antes ou depois."""


def _norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def separar(texto):
    t = texto.replace("\r", "").strip()
    t = re.sub(r"\A```(?:markdown|md)?\n(.*)\n```\Z", r"\1", t, flags=re.S).strip()
    m = re.match(r"\A---\n(.*?)\n---\n?(.*)\Z", t, re.S)
    return (m.group(1), m.group(2).strip()) if m else ("", t)


def chaves(fm):
    return [l.split(":", 1)[0].strip() for l in fm.splitlines() if re.match(r"^[A-Za-z_][\w-]*:", l)]


def estrutura(modelo):
    fm, corpo = separar(modelo)
    titulos = [(len(m.group(1)), m.group(2).strip()) for m in re.finditer(r"^(#{2,3})\s+(.+)$", corpo, re.M)]
    tabelas = []
    linhas = corpo.splitlines()
    for i, l in enumerate(linhas):
        if l.strip().startswith("|") and i + 1 < len(linhas) and re.match(r"^\|?\s*:?-{2,}", linhas[i + 1].strip().lstrip("|")):
            if not (i > 0 and linhas[i - 1].strip().startswith("|")):
                tabelas.append([c.strip() for c in l.strip().strip("|").split("|")])
    return {"chaves": chaves(fm), "titulos": titulos, "tabelas": tabelas}


def conferir(modelo, doc):
    """Lista do que o documento não tem do modelo (vazia = está encaixado)."""
    e = estrutura(modelo)
    fm, corpo = separar(doc)
    faltas = []
    if not fm:
        faltas.append("frontmatter (o documento precisa começar com ---)")
    ks = set(chaves(fm))
    faltas += [f"chave de frontmatter `{k}`" for k in e["chaves"] if k not in ks]
    tit_doc = [(len(m.group(1)), _norm(m.group(2))) for m in re.finditer(r"^(#{2,3})\s+(.+)$", corpo, re.M)]
    pos = 0
    for nivel, t in e["titulos"]:
        alvo = (nivel, _norm(t))
        try:
            pos = tit_doc.index(alvo, pos) + 1
        except ValueError:
            faltas.append(f"título `{'#' * nivel} {t}`" + (" (ou fora de ordem)" if alvo in tit_doc else ""))
    cab_doc = [_norm(" ".join(c.strip() for c in l.strip().strip("|").split("|")))
               for l in corpo.splitlines() if l.strip().startswith("|")]
    for cab in e["tabelas"]:
        if _norm(" ".join(cab)) not in cab_doc:
            faltas.append("tabela com as colunas " + " | ".join(cab))
    return faltas


def fixar_campos(doc, campos, modelo):
    """Grava no frontmatter os campos que o Atlas sabe (expert, oferta, data) e tira os que não existem no modelo."""
    fm, corpo = separar(doc)
    validas = set(chaves(separar(modelo)[0]))
    linhas = [l for l in fm.splitlines() if not re.match(r"^[A-Za-z_][\w-]*:", l) or l.split(":", 1)[0].strip() in validas]
    for k, v in campos.items():
        if k not in validas:
            continue
        nova = f'{k}: "{str(v).replace(chr(34), "")}"'
        i = next((j for j, l in enumerate(linhas) if l.split(":", 1)[0].strip() == k), None)
        if i is None: linhas.append(nova)
        else: linhas[i] = nova
    return "---\n" + "\n".join(linhas) + "\n---\n" + corpo + "\n"


def pedido(modelo, doc, faltas=None):
    extra = ""
    if faltas:
        extra = "\n\nNa tentativa anterior faltou isto do modelo. Corrija:\n" + "\n".join(f"- {f}" for f in faltas)
    return f"MODELO:\n\n{modelo}\n\n=====\n\nDOCUMENTO:\n\n{doc}{extra}"
