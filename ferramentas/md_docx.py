"""Leva as notas (.md) para .docx, para revisar no Google Docs ou no Word, e traz de volta.

Ida:   python3 md_docx.py ida  <pasta de notas> <pasta de destino>
Volta: python3 md_docx.py volta <arquivo.docx>            (imprime o markdown)

Cada linha da nota vira um parágrafo. Títulos (#, ##, ###) viram estilos de título; **negrito** vira negrito
de verdade. O resto (propriedades entre ---, listas com "- ", citações com ">", tabelas com |) fica como texto,
para a volta ser fiel.
"""
import re, sys, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
TIPOS = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
         '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
         '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
DOCRELS = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
           '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')


def _estilo(i, nome, tam, negrito=True, cor="000000"):
    return (f'<w:style w:type="paragraph" w:styleId="{i}"><w:name w:val="{nome}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
            f'<w:pPr><w:spacing w:before="240" w:after="80"/></w:pPr><w:rPr>{"<w:b/>" if negrito else ""}<w:color w:val="{cor}"/><w:sz w:val="{tam}"/></w:rPr></w:style>')


ESTILOS = (f'<?xml version="1.0" encoding="UTF-8"?><w:styles {W}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
           '<w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
           '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
           + _estilo("Heading1", "heading 1", 36) + _estilo("Heading2", "heading 2", 28) + _estilo("Heading3", "heading 3", 24)
           + '<w:style w:type="paragraph" w:styleId="Prop"><w:name w:val="Propriedade"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0"/></w:pPr>'
             '<w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/><w:color w:val="666666"/><w:sz w:val="18"/></w:rPr></w:style></w:styles>')


def _runs(txt):
    out = []
    for i, parte in enumerate(re.split(r"\*\*(.+?)\*\*", txt)):
        if parte:
            out.append(f'<w:r>{"<w:rPr><w:b/></w:rPr>" if i % 2 else ""}<w:t xml:space="preserve">{escape(parte)}</w:t></w:r>')
    return "".join(out)


def md_para_docx(md, destino):
    ps, fm, linhas = [], False, md.split("\n")
    for n, l in enumerate(linhas):
        if l.strip() == "---" and (n == 0 or fm):
            fm = n == 0
            ps.append('<w:p><w:pPr><w:pStyle w:val="Prop"/></w:pPr><w:r><w:t>---</w:t></w:r></w:p>')
            continue
        if fm:
            ps.append(f'<w:p><w:pPr><w:pStyle w:val="Prop"/></w:pPr><w:r><w:t xml:space="preserve">{escape(l)}</w:t></w:r></w:p>')
            continue
        if not l.strip():
            continue
        m = re.match(r"(#{1,3}) (.*)", l)
        if m:
            ps.append(f'<w:p><w:pPr><w:pStyle w:val="Heading{len(m.group(1))}"/></w:pPr><w:r><w:t xml:space="preserve">{escape(m.group(2))}</w:t></w:r></w:p>')
        else:
            ps.append(f"<w:p>{_runs(l)}</w:p>")
    doc = f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body>{"".join(ps)}<w:sectPr/></w:body></w:document>'
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", TIPOS); z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOCRELS); z.writestr("word/styles.xml", ESTILOS); z.writestr("word/document.xml", doc)


def docx_para_md(arq):
    import html
    x = zipfile.ZipFile(arq).read("word/document.xml").decode("utf-8")
    linhas = []
    for p in re.findall(r"<w:p[ >].*?</w:p>|<w:p/>", x, re.S):
        est = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        est = est.group(1) if est else ""
        txt = ""
        for r in re.findall(r"<w:r[ >].*?</w:r>", p, re.S):
            t = html.unescape("".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", r, re.S)))
            neg = bool(re.search(r"<w:b/>|<w:b w:val=\"(?:1|true)\"", r)) and not est.lower().startswith(("heading", "ttulo", "title"))
            txt += f"**{t}**" if neg and t.strip() else t
        txt = txt.replace("****", "")
        h = re.search(r"(\d)$", est) if est.lower().startswith(("heading", "ttulo")) else None
        linhas.append((("#" * int(h.group(1)) + " ") if h else "") + txt)
    out, fm = [], False
    junto = lambda a, b: any(a.startswith(c) and b.startswith(c) for c in ("- ", "> ", "|")) or re.match(r"\d+\. ", a) and re.match(r"\d+\. ", b)
    for i, l in enumerate(linhas):
        if not l.strip():
            continue
        if l.strip() == "---" and (not out or fm):
            fm = not out
            out.append("---" + ("" if fm else "\n"))
            continue
        if fm:
            out.append(l); continue
        if out and out[-1] and not out[-1].endswith("\n") and not junto(out[-1].split("\n")[-1], l):
            out.append("")
        out.append(l)
    return "\n".join(out).rstrip("\n") + "\n"


if __name__ == "__main__":
    if sys.argv[1] == "ida":
        origem, destino = Path(sys.argv[2]), Path(sys.argv[3])
        n = 0
        for p in sorted(origem.rglob("*.md")):
            alvo = destino / p.relative_to(origem).with_suffix(".docx")
            alvo.parent.mkdir(parents=True, exist_ok=True)
            md_para_docx(p.read_text(encoding="utf-8"), alvo); n += 1
        print(n, "documentos")
    else:
        sys.stdout.write(docx_para_md(sys.argv[2]))
