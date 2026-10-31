"""Agentes do Octopus IA que rodam de verdade no Codex.

Cada agente junta as instruções da sua skill (skills/<nome>/SKILL.md), o modelo que está no
cofre e as ferramentas que o servidor executa por ele. O Codex não lê nem grava arquivos:
os anexos chegam no texto da mensagem e ficam guardados na pasta da conversa para as ferramentas.
"""
import importlib.util, json, re, shutil, subprocess, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
from locais import LOCAL, python_whisper, ffmpeg as _ffmpeg, env_filho
CONVERSAS = LOCAL / "conversas"
FLOWS = LOCAL / "flows"
TEXTO_EXT = {".txt", ".md", ".srt", ".vtt", ".json", ".csv"}
IMAGEM_EXT = {".png", ".jpg", ".jpeg", ".webp"}
SKILLS = RAIZ / "skills"


def _carregar(caminho, nome):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def _sem_frontmatter(t):
    return re.sub(r"\A---\n.*?\n---\n", "", t, flags=re.S).strip()


def pasta_conversa(conversa):
    if not re.fullmatch(r"[a-z0-9]{4,40}", conversa or ""):
        raise ValueError("conversa inválida")
    return CONVERSAS / conversa


def pasta_inteligencia(flow, no):
    for x in (flow, no):
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,60}", str(x or "")):
            raise ValueError("identificador inválido")
    return FLOWS / flow / no


def nome_arquivo(nome):
    nome = Path(str(nome or "")).name.strip()
    if not nome or nome.startswith(".") or Path(nome).suffix.lower() not in TEXTO_EXT | IMAGEM_EXT:
        raise ValueError("Tipo de arquivo não aceito. Use .txt, .md, .srt, .vtt, .json, .csv, .png, .jpg ou .webp.")
    if re.search(r'[/\\:*?"<>|]', nome):
        raise ValueError("nome de arquivo inválido")
    return nome[:120]


def nome_anexo(nome):
    nome = Path(str(nome or "")).name.strip()
    if nome and not re.search(r"\.(txt|md|srt|vtt|json)$", nome, re.I):
        nome += ".txt"                      # texto colado no chat chega sem extensão
    if not nome or nome.startswith(".") or not re.fullmatch(r"[\w .()\-áéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]+\.(txt|md|srt|vtt|json)", nome, re.I):
        raise ValueError(f"anexo com nome não aceito: {nome}")
    return nome


# ---------------- Bíblia do nicho ----------------
MEDIR = {
    "type": "function",
    "name": "medir_blocos",
    "description": ("Mede o tempo (início e duração) e os caracteres de cada bloco de uma VSL. "
                    "Informe o anexo (nome do arquivo, como aparece na mensagem) ou o texto colado, e a lista "
                    "de blocos na ordem, cada um com as primeiras palavras exatas dele na transcrição. "
                    "Devolve a tabela pronta e os números em JSON."),
    "inputSchema": {
        "type": "object",
        "properties": {
            "anexo": {"type": "string", "description": "nome do arquivo anexado com a transcrição"},
            "texto": {"type": "string", "description": "texto da VSL, quando o usuário colou em vez de anexar"},
            "blocos": {"type": "array", "items": {"type": "object", "properties": {
                "bloco": {"type": "string"}, "inicio": {"type": "string"}}, "required": ["bloco", "inicio"]}},
            "duracao": {"type": "string", "description": "duração total do vídeo (mm:ss), só para texto sem marcação de tempo"},
        },
        "required": ["blocos"],
    },
}


def _instrucoes_biblia(cofre):
    skill = _sem_frontmatter((SKILLS / "biblia-do-nicho" / "SKILL.md").read_text(encoding="utf-8"))
    modelo = cofre / "Biblioteca" / "Modelos" / "Bíblia do nicho.md" if cofre else None
    modelo_txt = modelo.read_text(encoding="utf-8") if modelo and modelo.is_file() else "(modelo não encontrado no cofre)"
    est = cofre / "Biblioteca" / "Estruturas de VSL" if cofre else None
    estruturas = "\n\n".join(f"### {p.stem}\n{_sem_frontmatter(p.read_text(encoding='utf-8'))}" for p in sorted(est.glob("*.md")) if p.stem != "Estruturas de VSL") if est and est.is_dir() else "(a pasta Biblioteca/Estruturas de VSL ainda não existe)"
    return f"""Você é o agente Bíblia do nicho do Octopus IA. Responda sempre em português do Brasil.

{skill}

## Como você trabalha aqui dentro do Octopus IA
- Você não tem terminal nem internet. Os arquivos que você alcança são os da pasta do Octopus IA (regras mais abaixo). As transcrições chegam no texto da mensagem, cada uma com o nome do anexo.
- Para medir tempo e caracteres, chame a ferramenta `medir_blocos` (ela roda o `scripts/medir_blocos.py` por você). Passe `anexo` com o nome do arquivo, ou `texto` quando o usuário colou a VSL. Se ela disser que não achou o início de um bloco, corrija as primeiras palavras copiando exatamente da transcrição e chame de novo.
- Quando entregar a bíblia completa, a resposta deve ser só o documento em Markdown, começando pela linha `---` do frontmatter, sem texto antes nem depois. É isso que faz o botão **Salvar no Cérebro** aparecer para o usuário.
- Você só consulta o cofre para duas coisas, que já estão abaixo: o **modelo** (o formato exato da entrega) e a biblioteca de **estruturas e blocos de VSL** (para dar nome ao que a VSL tem). Você não sabe e não precisa saber qual projeto, expert ou oferta está aberto no Octopus IA: isso só é escolhido depois, na hora de gravar, e nunca entra no conteúdo da bíblia.
- Nicho, trechos, promessas e tudo o mais saem SÓ da VSL que o usuário mandou. Deixe `expert` e `oferta` vazios no frontmatter, a não ser que o usuário diga quais são na conversa.

## Modelo (Biblioteca/Modelos/Bíblia do nicho.md) — o formato da entrega
{modelo_txt}

## Biblioteca/Estruturas de VSL — estruturas e blocos que já têm nome (referência, não obrigação)
{estruturas}
"""


def _executor_biblia(pasta, cofre):
    medir = _carregar(SKILLS / "biblia-do-nicho" / "scripts" / "medir_blocos.py", "medir_blocos")

    def executar(nome, args):
        if nome != "medir_blocos":
            raise ValueError("ferramenta desconhecida")
        blocos = args.get("blocos")
        if not isinstance(blocos, list) or not blocos:
            raise ValueError("informe a lista de blocos")
        if args.get("anexo"):
            arq = pasta / "anexos" / nome_anexo(args["anexo"])
            if not arq.is_file():
                existentes = ", ".join(p.name for p in (pasta / "anexos").glob("*")) or "nenhum"
                raise ValueError(f"anexo não encontrado. Anexos desta conversa: {existentes}")
        elif args.get("texto"):
            arq = pasta / "colado.txt"; arq.write_text(str(args["texto"]), encoding="utf-8")
        else:
            raise ValueError("informe o anexo ou o texto da VSL")
        dur = medir.ts(args["duracao"]) if args.get("duracao") else None
        try:
            r = medir.medir(medir.ler_transcricao(str(arq)), blocos, dur)
        except SystemExit as e:
            raise ValueError(str(e))
        try:                                    # os blocos medidos (nome + primeiras palavras) vão para a tela: no chat da Bíblia, ela põe os títulos no arquivo da VSL
            (pasta / "blocos_vsl.json").write_text(json.dumps([{"bloco": str(b.get("bloco") or "")[:80], "inicio": str(b.get("inicio") or "")[:300]} for b in blocos if isinstance(b, dict)], ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return medir.tabela(r) + "\n\n" + json.dumps(r, ensure_ascii=False)
    return executar


# ---------------- Briefing da tese ----------------
LISTAR_BIBLIAS = {
    "type": "function",
    "name": "listar_biblias",
    "description": "Lista as bíblias do nicho que existem no cofre (dos projetos e dos exemplos), com nicho, expert e oferta de cada uma.",
    "inputSchema": {"type": "object", "properties": {}},
}
LER_BIBLIA = {
    "type": "function",
    "name": "ler_biblia",
    "description": "Lê uma bíblia do nicho do cofre. Use o caminho exatamente como veio de listar_biblias.",
    "inputSchema": {"type": "object", "properties": {"caminho": {"type": "string"}}, "required": ["caminho"]},
}


def _biblias(cofre):
    """Só arquivos de bíblia: Projetos/*/*/VSL/Bíblia do nicho*.md e Biblioteca/Exemplos/Bíblia do nicho*.md."""
    if not cofre or not cofre.is_dir():
        return []
    achados = list(cofre.glob("Projetos/*/*/VSL/Bíblia do nicho*.md")) + list(cofre.glob("Biblioteca/Exemplos/Bíblia do nicho*.md"))
    return sorted(achados, key=lambda p: p.stat().st_mtime, reverse=True)


def _campos(texto):
    m = re.match(r"\A---\n(.*?)\n---", texto, re.S)
    out = {}
    for l in (m.group(1).splitlines() if m else []):
        if ":" in l:
            k, v = l.split(":", 1); out[k.strip()] = v.strip().strip('"')
    return out


def skills_barra():
    """Skills que só rodam quando o usuário invoca com / no chat (frontmatter `barra: true`)."""
    out = []
    for p in sorted(SKILLS.glob("*/SKILL.md")):
        t = p.read_text(encoding="utf-8")
        c = _campos(t)
        if c.get("barra", "").lower() != "true":
            continue
        tit = re.search(r"^# (.+)$", t, re.M)
        out.append({"id": p.parent.name, "nome": tit.group(1).strip() if tit else p.parent.name, "resumo": c.get("resumo", ""), "categoria": c.get("categoria", ""),
                    "prefixo": "#" if c.get("prefixo", "").strip('"\'') == "#" else "/", "tipo": "funcao" if c.get("tipo", "") == "funcao" else "skill",
                    "agentes": [x.strip() for x in c.get("agentes", "").strip("[]").split(",") if x.strip()]})
    return out


def skill_invocada(texto, agentes_do_chat=(), cofre=None):
    """Se a mensagem traz /nome-da-skill, devolve o texto da skill (com as referências) para valer só neste pedido."""
    blocos = []
    for s in skills_barra():
        if not re.search(rf"(?:^|\s){re.escape(s['prefixo'])}{re.escape(s['id'])}(?![\w-])", str(texto or ""), re.I):
            continue
        if s["agentes"] and not set(s["agentes"]) & set(agentes_do_chat):      # skill de outro tipo de chat: não entra
            continue
        blocos.append(_bloco_skill(s, cofre, "invocada pelo usuário neste pedido"))
    return "\n\n".join(blocos)


def _bloco_skill(s, cofre, como):
    """O texto de uma skill ou função, com as referências e as notas da Biblioteca que ela usa."""
    if True:
        base = SKILLS / s["id"]
        partes = [f"### {'Função' if s['tipo'] == 'funcao' else 'Skill'} {como}: {s['prefixo']}{s['id']}\nSiga o que está abaixo neste pedido (e nas respostas de continuação dele). Não vale para outros pedidos.\n\n" + _sem_frontmatter((base / "SKILL.md").read_text(encoding="utf-8"))]
        for outra in [x.strip() for x in _campos((base / "SKILL.md").read_text(encoding="utf-8")).get("usa", "").strip("[]").split(",") if x.strip()]:
            alvo = SKILLS / outra / "SKILL.md"      # a função se apoia no manual de um agente (ex.: a bíblia do nicho): ele entra junto
            if re.fullmatch(r"[a-z0-9-]+", outra) and alvo.is_file():
                partes.append(f"#### Manual que esta função segue: {outra}\n" + _sem_frontmatter(alvo.read_text(encoding="utf-8")))
        for r in sorted((base / "referencias").glob("*.md")) if (base / "referencias").is_dir() else []:
            partes.append(f"#### referencias/{r.name}\n" + r.read_text(encoding="utf-8").strip())
        for nome in [x.strip() for x in _campos((base / "SKILL.md").read_text(encoding="utf-8")).get("biblioteca", "").strip("[]").split(",") if x.strip()]:
            nota = cofre / "Biblioteca" / f"{nome}.md" if cofre else None      # notas da Biblioteca que a skill usa: o usuário edita lá
            partes.append(f"#### Biblioteca/{nome} (nota do cofre)\n" + (_sem_frontmatter(nota.read_text(encoding="utf-8")) if nota and nota.is_file() else "(nota não encontrada na Biblioteca)"))
        return "\n\n".join(partes)


def funcoes_livres():
    """Funções (#) que valem em qualquer chat: o agente pode chamar sozinho quando o pedido for o trabalho de uma delas."""
    return [s for s in skills_barra() if s["tipo"] == "funcao" and not s["agentes"]]


def _instr_funcoes():
    fs = funcoes_livres()
    if not fs:
        return ""
    return ("\n\n**Funções do Octopus IA.** Cada função traz o passo a passo e o formato de um trabalho. Quando o pedido do usuário for o trabalho de uma delas, "
            "chame você mesmo a ferramenta `usar_funcao` com o id, antes de fazer o trabalho, e siga o que ela devolver. "
            "Nunca peça ao usuário para digitar a função: ele não precisa chamar nada. Se a função já veio no pedido (invocada pelo usuário), não chame de novo.\n"
            + "\n".join(f"- `{f['id']}`: {f['resumo']}" for f in fs))


def _instrucoes_briefing(cofre):
    skill = _sem_frontmatter((SKILLS / "briefing-de-tese" / "SKILL.md").read_text(encoding="utf-8"))
    modelo = cofre / "Biblioteca" / "Modelos" / "Briefing de tese.md" if cofre else None
    modelo_txt = modelo.read_text(encoding="utf-8") if modelo and modelo.is_file() else "(modelo não encontrado no cofre)"
    return f"""Você é o agente Briefing da tese do Octopus IA. Responda sempre em português do Brasil, de forma direta.

{skill}

## Como você trabalha aqui dentro do Octopus IA
- Você não tem terminal nem internet. Os arquivos que você alcança são os da pasta do Octopus IA (regras mais abaixo). Para ver as bíblias use as ferramentas `listar_biblias` e `ler_biblia`. Elas só enxergam bíblias do nicho.
- A primeira mensagem da conversa traz o projeto aberto no Octopus IA (expert, oferta e nicho). Use isso para sugerir a bíblia certa.
- Quando entregar o briefing completo, a resposta deve ser só o documento em Markdown, começando pela linha `---` do frontmatter, sem texto antes nem depois. É isso que faz o botão **Salvar no Cérebro** aparecer.
- Nas etapas da conversa, responda normalmente, sem frontmatter.

## Modelo atual do cofre (Biblioteca/Modelos/Briefing de tese.md)
{modelo_txt}
"""


def lista_biblias(cofre):
    out = []
    for p in _biblias(cofre):
        c = _campos(p.read_text(encoding="utf-8"))
        rot = " · ".join(x for x in [c.get("nicho"), c.get("expert"), c.get("oferta")] if x) or p.stem
        out.append({"caminho": p.relative_to(cofre).as_posix(), "rotulo": rot + (" (exemplo)" if p.parts[-2] == "Exemplos" else "")})
    return out


def _executor_briefing(pasta, cofre):
    def biblias():
        """Com o nó Oferta ligado, só as bíblias daquela oferta (e os exemplos da Biblioteca)."""
        try:
            o = json.loads((pasta / "oferta.json").read_text(encoding="utf-8"))
            base = cofre / "Projetos" / o["expert"] / o["oferta"]
        except (OSError, ValueError, KeyError):
            return _biblias(cofre)
        return [p for p in _biblias(cofre) if base in p.parents or "Biblioteca" in p.relative_to(cofre).parts[:1]]

    def executar(nome, args):
        if nome == "listar_biblias":
            itens = []
            for p in biblias():
                c = _campos(p.read_text(encoding="utf-8"))
                itens.append({"caminho": p.relative_to(cofre).as_posix(), "nicho": c.get("nicho", ""),
                              "expert": c.get("expert", ""), "oferta": c.get("oferta", ""),
                              "exemplo": p.parts[-2] == "Exemplos"})
            return json.dumps(itens, ensure_ascii=False) if itens else "Nenhuma bíblia do nicho no cofre."
        if nome == "ler_biblia":
            rel = str(args.get("caminho") or "")
            permitidos = {p.relative_to(cofre).as_posix(): p for p in biblias()}
            if rel not in permitidos:
                raise ValueError("caminho não é uma bíblia do cofre. Use um caminho de listar_biblias.")
            return permitidos[rel].read_text(encoding="utf-8")
        raise ValueError("ferramenta desconhecida")
    return executar


# ---------------- Copy de anúncio (aba Criativos) ----------------
def _f(nome, desc, props=None, obrig=None):
    return {"type": "function", "name": nome, "description": desc,
            "inputSchema": {"type": "object", "properties": props or {}, **({"required": obrig} if obrig else {})}}


FERR_ANUNCIO = [
    _f("listar_narrativas", "Lista as narrativas da biblioteca do cofre, primeiro as validadas: número, nome, situação (validada ou não atualizada), grupo (o trabalho que fazem), quando usar, quantos exemplos reais têm e a média de palavras e de tempo desses exemplos."),
    _f("ler_narrativa", "Abre uma narrativa: a ideia, a estrutura (batidas), a média de palavras e de tempo dos exemplos reais e alguns exemplos inteiros. Use o nome ou o número de listar_narrativas.",
       {"nome": {"type": "string"}, "exemplos": {"type": "integer", "description": "quantos exemplos trazer (1 a 5, padrão 3)"}}, ["nome"]),
    _f("listar_formatos", "Lista os formatos da biblioteca do cofre, primeiro os validados: nome, situação (validada ou não atualizada), categoria, o sinal visual que identifica cada um e com o que se confunde."),
    _f("ler_formato", "Abre a nota de um formato: como gravar, quem aparece, o que não pode faltar, como marcar no roteiro e o exemplo roteirizado.", {"nome": {"type": "string"}}, ["nome"]),
    _f("listar_angulos", "Lista os ângulos da biblioteca do cofre (por onde o anúncio entra no assunto), primeiro os validados (História emocional, Conspiracional, Científico, Notícia): nome, situação (validada ou não atualizada), onde se usa e a ideia em uma linha.",
       {"categoria": {"type": "string", "description": "opcional: Problema | Solução | Clique | CTA | Gancho"}}),
    _f("ler_angulo", "Abre um ângulo: a ideia, quando usar e o exemplo. Use o nome ou o número de listar_angulos.", {"nome": {"type": "string"}}, ["nome"]),
    _f("listar_ganchos", "Lista as notas de ganchos da biblioteca (Biblioteca/Ganchos): fórmulas de abertura por gatilho (Recompensa, Mistério, Crenças, Disrupção, Reconhecimento) e a lista geral de fórmulas prontas. Traz o nome de cada nota e as fórmulas dela."),
    _f("ler_gancho", "Abre uma nota de ganchos com as fórmulas e os exemplos. Na lista geral (centenas de fórmulas), passe `busca` com uma palavra (erro, segredo, ninguém, pare…) para trazer só as que a contêm.",
       {"nome": {"type": "string"}, "busca": {"type": "string", "description": "opcional: palavra para filtrar as fórmulas"}}, ["nome"]),
    _f("ler_dicionario_da_oferta", "Lê o Dicionário da oferta: jeito de falar do expert, troca de palavras, comparações, provas à mão, o que não passa e o placar dos anúncios. Leia antes de escrever qualquer texto para a oferta. Se não existir, a ferramenta avisa.",
       {"expert": {"type": "string", "description": "só se não houver nó Oferta ligado"}, "oferta": {"type": "string", "description": "só se não houver nó Oferta ligado"}}),
    _f("listar_personas", "Lista as personas da oferta (nome e resumo) e, se pedir uma pelo nome, traz o texto inteiro dela.",
       {"nome": {"type": "string", "description": "opcional: o nome da persona para ler inteira"}, "expert": {"type": "string"}, "oferta": {"type": "string"}}),
    _f("listar_oferta", "Lista as notas da oferta ligada a este flow (big ideas, anúncios com status, bíblia do nicho, briefing de tese). Só funciona com um nó Oferta ligado ao chat."),
    _f("ler_nota_oferta", "Lê uma nota da oferta ligada a este flow. Use o caminho exatamente como veio de listar_oferta.", {"caminho": {"type": "string"}}, ["caminho"]),
    _f("ler_controle_de_mercado", "Controle de mercado de uma oferta: as ideias de cada categoria (dores, desejos, promessas, provas, mecanismo, soluções comuns) com quantos anúncios da base usam cada uma e os trechos exatos que mais se repetem, os argumentos idênticos, as narrativas e a lista dos anúncios registrados. Use para classificar anúncio novo com os mesmos nomes de ideia, para auditar um anúncio e para criar anúncio com o que está validado.",
       {"base": {"type": "string", "description": "de quais anúncios: todos (padrão) | meus | validados (os meus marcados como validados) | concorrentes | anunciante:<nome do concorrente>"},
        "expert": {"type": "string", "description": "só se não houver nó Oferta ligado"}, "oferta": {"type": "string", "description": "só se não houver nó Oferta ligado"}}),
    _f("ler_anuncio_do_controle", "Lê um anúncio registrado no controle de mercado, inteiro: transcrição, narrativa e elementos. Use o número (n) de ler_controle_de_mercado, com a mesma base.",
       {"n": {"type": "integer"}, "base": {"type": "string"}, "expert": {"type": "string"}, "oferta": {"type": "string"}}, ["n"]),
    _f("atualizar_anuncio", "Atualiza um anúncio já salvo na oferta: a fase (status), o tempo exato medido no vídeo gravado, as palavras, a versão da VSL e os números de tráfego (gasto, faturamento, hook_rate, hold_rate, ic, ctr, cpa, cpm, conversao_checkout) e de VSL (play_rate, retencao_1min, retencao_pitch, conversao). Não mexe no roteiro.",
       {"anuncio": {"type": "string", "description": "o id (AD07) ou parte do título"},
        "status": {"type": "string", "description": "para gravação | gravado | para edição | editado | no ar | validou | não validou"},
        "tempo": {"type": "string", "description": "duração exata do vídeo gravado, ex.: 1min27"}, "palavras": {"type": "integer"},
        "vsl": {"type": "string", "description": "versão da VSL para onde o anúncio manda, ex.: V2"},
        "gasto": {"type": "number"}, "faturamento": {"type": "number"}, "ctr": {"type": "number", "description": "em %"},
        "hook_rate": {"type": "number", "description": "em %"}, "hold_rate": {"type": "number", "description": "em %"},
        "ic": {"type": "number", "description": "custo por início de checkout (initiate checkout), em reais"}, "cpa": {"type": "number", "description": "custo por compra, em reais"},
        "cpm": {"type": "number", "description": "custo por mil impressões, em reais"}, "conversao_checkout": {"type": "number", "description": "taxa de conversão do checkout (compras ÷ inícios de checkout), em %"},
        "play_rate": {"type": "number", "description": "quem deu play na VSL, em %"}, "retencao_1min": {"type": "number", "description": "retenção no primeiro minuto da VSL, em %"},
        "retencao_pitch": {"type": "number", "description": "retenção até o pitch da VSL, em %"}, "conversao": {"type": "number", "description": "taxa de conversão da VSL, em %"},
        "expert": {"type": "string", "description": "só se não houver nó Oferta ligado"}, "oferta": {"type": "string", "description": "só se não houver nó Oferta ligado"}}, ["anuncio"]),
]
PPM = 170          # palavras por minuto de fala em anúncio


def _secao(texto, titulo):
    m = re.search(rf"^## {re.escape(titulo)}\s*\n(.*?)(?=^## |\Z)", texto, re.S | re.M)
    return m.group(1).strip() if m else ""


def _exemplos(texto):
    """Exemplos reais da nota de narrativa: [(título, formato/por quê, fala)]."""
    out = []
    for bloco in re.split(r"^### ", _secao(texto, "Exemplo"), flags=re.M)[1:]:
        linhas = bloco.splitlines()
        fala = " ".join(l[1:].strip() for l in linhas if l.startswith(">")).strip()
        if len(fala.split()) >= 40:
            meta = " ".join(l.strip() for l in linhas[1:] if l.strip() and not l.startswith(">"))[:400]
            out.append((linhas[0].strip(), meta, fala))
    return out


def _tempo(palavras):
    s = round(palavras / PPM * 60)
    return f"{s // 60}min{s % 60:02d}" if s >= 60 else f"{s}s"


def _regua(exs):
    if not exs:
        return None
    n = sorted(len(e[2].split()) for e in exs)
    media = round(sum(n) / len(n))
    return {"exemplos": len(n), "media_palavras": media, "faixa_palavras": f"{n[0]} a {n[-1]}", "tempo_medio": _tempo(media)}


def _notas(cofre, pasta, tipo):
    """As notas de uma pasta da Biblioteca: primeiro as da raiz (as validadas), depois as das subpastas (as não atualizadas)."""
    base = cofre / "Biblioteca" / pasta if cofre else None
    if not base or not base.is_dir():
        return []
    out = []
    for p in sorted(base.glob("*.md")) + sorted(x for x in base.rglob("*.md") if x.parent != base):
        t = p.read_text(encoding="utf-8")
        if _campos(t).get("tipo", "").strip('"') == tipo:
            out.append((p, t))
    return out


def _situacao(p, pasta):
    return "validada" if p.parent.name == pasta else "não atualizada"


def _achar_nota(notas, nome):
    alvo = re.sub(r"[^a-z0-9]+", " ", _sem_acento(str(nome or "")).lower()).strip()
    if not alvo:
        return None
    norm = lambda p: re.sub(r"[^a-z0-9]+", " ", _sem_acento(p.stem).lower()).strip()
    for p, t in notas:
        if norm(p) == alvo:
            return p, t
    num = re.fullmatch(r"0*(\d+)", alvo)
    for p, t in notas:
        n = norm(p)
        if (num and re.match(rf"0*{num.group(1)}\b", n)) or alvo in n or re.sub(r"^\d+\s*", "", n) == alvo:
            return p, t
    return None


def _sem_acento(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def pasta_oferta(cofre, expert, oferta):
    """Projetos/{Expert}/{Oferta} dentro do cofre, ou None."""
    if not cofre or not expert or not oferta:
        return None
    for x in (expert, oferta):
        if re.search(r'[/\\:*?"<>|]', str(x)) or str(x).startswith("."):
            return None
    p = cofre / "Projetos" / str(expert) / str(oferta)
    try:
        p.resolve().relative_to(cofre.resolve())
    except ValueError:
        return None
    return p if p.is_dir() else None


def _instrucoes_anuncio(cofre):
    base = SKILLS / "anuncio"
    skill = _sem_frontmatter((base / "SKILL.md").read_text(encoding="utf-8"))
    le = lambda p: p.read_text(encoding="utf-8") if p.is_file() else "(não encontrado)"
    vicios = le(cofre / "Biblioteca" / "Vícios de IA.md") if cofre else "(sem cofre)"
    return f"""Você é o agente Copy de anúncio do Octopus IA. Responda sempre em português do Brasil.

{skill}

## Como você trabalha aqui dentro do Octopus IA
- Você não tem terminal nem internet. Os arquivos que você alcança são os da pasta do Octopus IA (regras mais abaixo). O material do flow chega no texto da mensagem, marcado como contexto. As bibliotecas do cofre você consulta pelas ferramentas.
- Não mostre a divisão do seu raciocínio em etapas longas: combine a escolha em poucas linhas e escreva.
- Quando entregar os anúncios (ou as big ideas para guardar, ou o controle de mercado), a resposta é só o documento, começando pela linha `---`.

## referencias/publico.md
{le(base / "referencias" / "publico.md")}

## referencias/revisao.md
{le(base / "referencias" / "revisao.md")}

## Biblioteca/Vícios de IA (nota do cofre)
{vicios}
"""


def _executor_anuncio(pasta, cofre):
    def oferta():
        try:
            o = json.loads((pasta / "oferta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return pasta_oferta(cofre, o.get("expert"), o.get("oferta"))

    def notas_oferta(base):
        out = []
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(base)
            if rel.parts[0] == "Atlas" or any(x.startswith(".") for x in rel.parts):      # conversas e flows do app ficam de fora
                continue
            c = _campos(p.read_text(encoding="utf-8"))
            out.append({"caminho": rel.as_posix(), "tipo": c.get("tipo", "").strip('"'), **({"status": c["status"].strip('"')} if c.get("status") else {})})
        return out

    def executar(nome, args):
        if nome == "listar_narrativas":
            idx = (cofre / "Biblioteca" / "Narrativas" / "Narrativas.md") if cofre else None
            usar = {}
            if idx and idx.is_file():                          # "quando usar", do índice
                for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*[—-]\s*(.+)", idx.read_text(encoding="utf-8")):
                    usar[m.group(1).strip()] = m.group(2).strip()
            itens = []
            for p, t in _notas(cofre, "Narrativas", "narrativa"):
                c = _campos(t)
                itens.append({"nome": p.stem, "situacao": _situacao(p, "Narrativas"), "grupo": c.get("grupo", "").strip('"'), "quando_usar": usar.get(p.stem, ""), **(_regua(_exemplos(t)) or {"exemplos": 0})})
            return json.dumps(itens, ensure_ascii=False) if itens else "Nenhuma narrativa em Biblioteca/Narrativas."
        if nome == "ler_narrativa":
            achou = _achar_nota(_notas(cofre, "Narrativas", "narrativa"), args.get("nome"))
            if not achou:
                raise ValueError("narrativa não encontrada. Use um nome de listar_narrativas.")
            p, t = achou
            exs = _exemplos(t)
            try:
                k = max(1, min(5, int(args.get("exemplos") or 3)))
            except (TypeError, ValueError):
                k = 3
            r = _regua(exs)
            # exemplos espalhados pela nota (ofertas diferentes), não só os primeiros
            passo = max(1, len(exs) // k)
            escolhidos = exs[::passo][:k]
            partes = [f"# {p.stem} ({_situacao(p, 'Narrativas')})", "## A ideia\n" + _secao(t, "A ideia"), "## Estrutura\n" + _secao(t, "Estrutura")]
            partes.append("## Régua (dos exemplos reais)\n" + (f"{r['exemplos']} exemplos · média de {r['media_palavras']} palavras ({r['tempo_medio']} a {PPM} palavras/min) · de {r['faixa_palavras']} palavras"
                          if r else "Sem exemplos reais suficientes: use as faixas padrão da skill."))
            if _secao(t, "Inteligência acumulada"):
                partes.append("## Inteligência acumulada\n" + _secao(t, "Inteligência acumulada")[:3000])
            for tit, meta, fala in escolhidos:
                partes.append(f"## Exemplo: {tit} ({len(fala.split())} palavras)\n{meta}\n\n> {fala}")
            return "\n\n".join(partes)
        if nome == "listar_formatos":
            itens = []
            for p, t in _notas(cofre, "Formatos", "formato"):
                sinal = re.search(r"\*\*Sinal:\*\*\s*(.+)", t)
                conf = re.search(r"\*\*Confunde com:\*\*\s*(.+)", t)
                itens.append({"nome": p.stem, "situacao": _situacao(p, "Formatos"), "categoria": _campos(t).get("categoria", "").strip('"'),
                              "sinal": sinal.group(1).strip() if sinal else "", "confunde_com": conf.group(1).strip() if conf else ""})
            return json.dumps(itens, ensure_ascii=False) if itens else "Nenhum formato em Biblioteca/Formatos."
        if nome == "ler_formato":
            achou = _achar_nota(_notas(cofre, "Formatos", "formato"), args.get("nome"))
            if not achou:
                raise ValueError("formato não encontrado. Use um nome de listar_formatos.")
            t = re.sub(r"\n## Anúncios neste formato.*", "", achou[1], flags=re.S)
            return t[:14000]
        if nome == "listar_angulos":
            cat = _sem_acento(str(args.get("categoria") or "")).lower()
            itens = []
            for p, t in _notas(cofre, "Ângulos", "angulo"):
                c = _campos(t)
                if cat and _sem_acento(c.get("categoria", "").strip('"')).lower() != cat:
                    continue
                itens.append({"nome": p.stem, "situacao": _situacao(p, "Ângulos"), "categoria": c.get("categoria", "").strip('"'), "onde": c.get("onde", "").strip('"'), "ideia": _secao(t, "A ideia")})
            return json.dumps(itens, ensure_ascii=False) if itens else "Nenhum ângulo em Biblioteca/Ângulos."
        if nome == "ler_angulo":
            achou = _achar_nota(_notas(cofre, "Ângulos", "angulo"), args.get("nome"))
            if not achou:
                raise ValueError("ângulo não encontrado. Use um nome de listar_angulos.")
            return re.sub(r"\n## Anúncios com este ângulo.*", "", achou[1], flags=re.S)
        if nome == "listar_ganchos":
            itens = []
            for p, t in _notas(cofre, "Ganchos", "gancho"):
                formulas = re.findall(r"^### (.+)$", t, re.M)
                itens.append({"nome": p.stem, "ideia": _secao(t, "A ideia"), "formulas": formulas or f"{_campos(t).get('formulas', '?')} fórmulas numeradas: abra com ler_gancho e `busca`"})
            return json.dumps(itens, ensure_ascii=False) if itens else "Nenhuma nota em Biblioteca/Ganchos."
        if nome == "ler_gancho":
            achou = _achar_nota(_notas(cofre, "Ganchos", "gancho"), args.get("nome"))
            if not achou:
                raise ValueError("nota de ganchos não encontrada. Use um nome de listar_ganchos.")
            t, busca = achou[1], _sem_acento(str(args.get("busca") or "")).lower().strip()
            if busca:
                linhas = [l for l in t.splitlines() if busca in _sem_acento(l).lower()]
                return "\n".join(linhas[:120]) or f"Nenhuma fórmula com '{args.get('busca')}' nesta nota."
            return t if len(t) <= 20000 else t[:20000] + "\n\n(continua: use `busca` para filtrar)"
        if nome in ("ler_dicionario_da_oferta", "listar_personas"):
            import criativos
            base = oferta() or (pasta_oferta(cofre, args.get("expert"), args.get("oferta")) if args.get("expert") and args.get("oferta") else None)
            if not base:
                return ("Não sei de qual oferta: não há nó Oferta ligado a este chat (ou a oferta informada não existe). "
                        "Pergunte ao usuário o expert e a oferta (listar_cofre mostra as que existem) e chame de novo com expert e oferta.")
            if nome == "ler_dicionario_da_oferta":
                arq = base / "Dicionário da oferta.md"
                if not arq.is_file():
                    return (f"A oferta {base.name} ainda não tem Dicionário da oferta. Diga isso ao usuário e ofereça montar agora "
                            "(seção \"Dicionário da oferta\" da skill), ou seguir sem ele.")
                return arq.read_text(encoding="utf-8")[:40000]
            ps = criativos.personas(cofre, base.parent.name, base.name)
            if not ps:
                return "Esta oferta ainda não tem personas. Elas são criadas na aba Criativos › Personas."
            if args.get("nome"):
                alvo = _sem_acento(str(args["nome"]).lstrip("@")).lower()
                p = next((x for x in ps if _sem_acento(x["nome"]).lower() == alvo), None) or next((x for x in ps if alvo in _sem_acento(x["nome"]).lower()), None)
                if not p:
                    raise ValueError("persona não encontrada. Nomes: " + ", ".join(x["nome"] for x in ps))
                return f"# {p['nome']}\n{p['resumo']}\n\n{p['texto']}"
            return json.dumps([{"nome": x["nome"], "resumo": x["resumo"]} for x in ps], ensure_ascii=False)
        if nome == "atualizar_anuncio":
            import criativos
            base = oferta() or (pasta_oferta(cofre, args.get("expert"), args.get("oferta")) if args.get("expert") and args.get("oferta") else None)
            if not base:
                return "Não sei de qual oferta é o anúncio: não há nó Oferta ligado a este chat. Pergunte o expert e a oferta e chame de novo."
            try:
                rel = criativos.atualizar_anuncio(cofre, base.parent.name, base.name, args.get("anuncio"), args)
            except criativos.ErroCriativos as e:
                raise ValueError(str(e))
            return f"Atualizado: {rel}"
        if nome in ("ler_controle_de_mercado", "ler_anuncio_do_controle"):
            import controle
            base = oferta() or (pasta_oferta(cofre, args.get("expert"), args.get("oferta")) if args.get("expert") and args.get("oferta") else None)      # com o nó Oferta, vale só a oferta do nó
            if not base:
                return ("Não sei de qual oferta é o controle de mercado: não há nó Oferta ligado a este chat (ou a oferta informada não existe). "
                        "Pergunte ao usuário o expert e a oferta (listar_cofre mostra as que existem) e chame de novo com expert e oferta.")
            filtro = str(args.get("base") or "").strip()
            filtro = "" if filtro.lower() == "todos" else filtro
            if nome == "ler_anuncio_do_controle":
                d = controle.dados(cofre, base.parent.name, base.name, filtro)
                a = next((x for x in d["ads"] if x["n"] == args.get("n")), None)
                if not a:
                    raise ValueError("anúncio não encontrado nessa base. Use um n de ler_controle_de_mercado.")
                por = (d["narr"] or {"por": {}})["por"].get(a["n"], {})
                nar = next((x for x in (d["narr"] or {"lista": []})["lista"] if a["n"] in x["ads"]), None)
                els = {c: [x["t"] for x in d["geral"][c] if a["n"] in x["a"]] for c in d["geral"]}
                return json.dumps({"n": a["n"], "titulo": a["titulo"], "origem": a["origem"], "anunciante": a["anunciante"], "validado": a["validado"],
                                   "narrativa": nar and nar["nome"], "formato": por.get("formato"), "elementos": els, "transcricao": a["texto"]}, ensure_ascii=False)
            r = controle.resumo(cofre, base.parent.name, base.name, filtro)
            if not r["anuncios"]:
                return ("O controle de mercado desta oferta ainda está vazio: estes são os primeiros anúncios. Crie os nomes das ideias." if not filtro
                        else "Nenhum anúncio nessa base. O que há na oferta: " + json.dumps(r["na_oferta"], ensure_ascii=False))
            return json.dumps(r, ensure_ascii=False)
        if nome in ("listar_oferta", "ler_nota_oferta"):
            base = oferta()
            if not base:
                return "Não há nó Oferta ligado a este chat (ou a pasta da oferta não existe no cofre). Trabalhe com o material do flow."
            if nome == "listar_oferta":
                itens = notas_oferta(base)
                return json.dumps({"oferta": base.relative_to(cofre).as_posix(), "notas": itens}, ensure_ascii=False) if itens else "A oferta ainda não tem notas."
            rel = str(args.get("caminho") or "")
            if rel not in {i["caminho"] for i in notas_oferta(base)}:
                raise ValueError("caminho não é uma nota desta oferta. Use um caminho de listar_oferta.")
            return (base / rel).read_text(encoding="utf-8")[:60000]
        raise ValueError("ferramenta desconhecida")
    return executar


# ---------------- YouTube (nó do flow de Criativos) ----------------
YTDLP = [str(python_whisper()), "-m", "yt_dlp"]
if _ffmpeg():                                   # o ffmpeg que veio com a instalação (junta vídeo e áudio ao baixar)
    YTDLP += ["--ffmpeg-location", _ffmpeg()]
if shutil.which("node"):                        # o YouTube pede um runtime de JavaScript; o Node já é requisito do Octopus IA
    YTDLP += ["--js-runtimes", "node"]
FERR_YOUTUBE = [_f("buscar_youtube", "Busca vídeos no YouTube por um termo e devolve, de cada um: link, título, canal, visualizações e duração em segundos.",
                   {"termo": {"type": "string", "description": "o termo de busca, como a pessoa digitaria no YouTube"},
                    "quantidade": {"type": "integer", "description": "quantos vídeos trazer (1 a 40, padrão 20)"},
                    "tipo": {"type": "string", "enum": ["todos", "shorts", "longos"], "description": "shorts = até 3 minutos; longos = acima de 3 minutos; padrão todos"}}, ["termo"]),
                _f("baixar_video", "Baixa um vídeo do YouTube (MP4, até 1080p) para a pasta Downloads/YouTube, dentro da pasta de arquivos do Octopus IA. Não dá para escolher outro lugar.",
                   {"link": {"type": "string", "description": "o link do vídeo no YouTube"}}, ["link"])]
INSTR_YOUTUBE = """## Nó YouTube ligado a este chat
Você pode buscar vídeos no YouTube com a ferramenta `buscar_youtube`.
- Use quando o usuário pedir para buscar, achar ou trazer vídeos, virais ou referências do YouTube. O termo é o que ele disser; se pedir um nicho, use o jeito que o público busca. Se ele falar em Shorts ou vídeos curtos, use tipo "shorts".
- Mostre o resultado numa tabela em Markdown: vídeo (link clicável com o título), canal, visualizações e duração. Ordene por visualizações, a não ser que ele peça outro critério.
- Não invente vídeo, link nem número: só o que a ferramenta devolveu. Você não assistiu aos vídeos; para analisar um deles, o usuário precisa transcrever (nó Transcrição) e ligar no chat.
- **Baixar vídeo:** quando o usuário pedir para baixar um ou mais vídeos, use `baixar_video`. O vídeo é salvo sempre em Downloads/YouTube, dentro da pasta de arquivos do Octopus IA: não pergunte onde salvar e, se o usuário pedir outra pasta, diga que o Octopus só grava na pasta dele. Baixe um vídeo por chamada e, no fim, diga o nome do arquivo e que está em Downloads/YouTube na pasta do Octopus IA. Só baixa links do YouTube."""


def buscar_youtube(termo, quantidade=20, tipo="todos"):
    """Busca pelo yt-dlp (sem chave e sem navegador). Devolve a lista ordenada por visualizações."""
    import subprocess
    termo = re.sub(r"\s+", " ", str(termo or "")).strip()[:100]
    if not termo:
        raise ValueError("Diga o termo da busca.")
    try:
        quantidade = max(1, min(40, int(quantidade or 20)))
    except (TypeError, ValueError):
        quantidade = 20
    tipo = tipo if tipo in ("shorts", "longos") else "todos"
    if not Path(YTDLP[0]).exists():
        raise ValueError("O buscador do YouTube não está instalado no Octopus IA. Peça ao Claude Code ou ao Codex para rodar a instalação do Octopus IA de novo (instalar.py).")
    puxar = quantidade if tipo == "todos" else min(120, max(30, quantidade * 3))     # filtro por duração precisa de mais resultados
    busca = termo + " #shorts" if tipo == "shorts" else termo                      # a busca comum quase não traz vídeo curto
    try:
        r = subprocess.run(YTDLP + ["--flat-playlist", "--dump-single-json", "--no-warnings", "--extractor-args", "youtube:lang=pt",
                                    f"ytsearch{puxar}:{busca}"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env_filho(), timeout=90)
        dados = json.loads(r.stdout or "{}")
    except (subprocess.SubprocessError, ValueError, OSError):
        raise ValueError("O YouTube não respondeu à busca. Tente de novo em instantes.")
    itens = []
    for e in dados.get("entries") or []:
        if not isinstance(e, dict) or not e.get("id") or e.get("live_status") in ("is_live", "is_upcoming"):
            continue
        dur = e.get("duration")
        if (tipo == "shorts" and not (dur and dur <= 180)) or (tipo == "longos" and not (dur and dur > 180)):
            continue
        itens.append({"link": f"https://www.youtube.com/watch?v={e['id']}", "titulo": str(e.get("title") or "")[:140],
                      "canal": e.get("channel") or e.get("uploader") or "", "visualizacoes": e.get("view_count"),
                      "segundos": int(dur) if dur else None})
    itens.sort(key=lambda x: -(x["visualizacoes"] or 0))
    return itens[:quantidade]


PASTAS_NOME = {"downloads": "Downloads", "download": "Downloads", "transferencias": "Downloads", "mesa": "Desktop", "area de trabalho": "Desktop",
               "desktop": "Desktop", "documentos": "Documents", "documents": "Documents", "filmes": "Movies", "movies": "Movies", "videos": "Movies"}


def pasta_destino(texto):
    """Onde o usuário quer salvar: um nome conhecido (Downloads, Mesa…) ou um caminho DENTRO da pasta dele. Nada fora dela."""
    casa = Path.home().resolve()
    t = str(texto or "").strip().strip('"\'')
    chave = re.sub(r"[^a-z ]+", "", _sem_acento(t).lower()).strip()
    if not t or chave in PASTAS_NOME:
        p = casa / PASTAS_NOME.get(chave, "Downloads")
    else:
        p = Path(t).expanduser()
        if not p.is_absolute():                 # "Documentos/Referências" → a pasta Documentos de verdade, não uma nova
            partes = p.parts
            prim = PASTAS_NOME.get(re.sub(r"[^a-z ]+", "", _sem_acento(partes[0]).lower()).strip(), partes[0])
            p = casa.joinpath(prim, *partes[1:])
    p = p.resolve()
    try:
        rel = p.relative_to(casa)
    except ValueError:
        raise ValueError("Só dá para salvar dentro da pasta do usuário (Downloads, Mesa, Documentos, Filmes ou uma subpasta delas).")
    if not rel.parts or any(x.startswith(".") for x in rel.parts) or rel.parts[0] == "Library":
        raise ValueError("Essa pasta não pode ser usada. Escolha Downloads, Mesa, Documentos, Filmes ou uma subpasta delas.")
    return p


def baixar_video(link, cofre):
    """Baixa um vídeo do YouTube em MP4 (até 1080p) em Downloads/YouTube, dentro da pasta do Octopus IA. Devolve arquivo, tamanho, resolução e duração."""
    import subprocess, urllib.parse
    link = str(link or "").strip()
    u = urllib.parse.urlparse(link)
    if u.scheme != "https" or u.netloc.lower() not in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
        raise ValueError("Só dá para baixar links do YouTube (https://www.youtube.com/… ou https://youtu.be/…).")
    if not cofre or not Path(cofre).is_dir():
        raise ValueError("A pasta de arquivos do Octopus IA não está configurada.")
    destino = Path(cofre) / "Downloads" / "YouTube"
    if not Path(YTDLP[0]).exists():
        raise ValueError("O baixador do YouTube não está instalado no Octopus IA. Peça ao Claude Code ou ao Codex para rodar a instalação do Octopus IA de novo (instalar.py).")
    destino.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(YTDLP + ["--no-warnings", "--no-playlist", "--no-overwrites", "--max-filesize", "3G",
                                    "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--merge-output-format", "mp4",
                                    "--print", "after_move:%(filepath)s\t%(height)s\t%(duration)s",
                                    "-o", str(destino / "%(title).80s [%(id)s].%(ext)s"), "--", link],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env_filho(), timeout=1200)
    except subprocess.TimeoutExpired:
        raise ValueError("O download passou de 20 minutos e foi cancelado.")
    linha = next((l for l in reversed((r.stdout or "").splitlines()) if "\t" in l), "")
    arq = Path(linha.split("\t")[0]) if linha else None
    if r.returncode != 0 or not arq or not arq.is_file():
        erro = ((r.stderr or "").strip().splitlines() or ["motivo desconhecido"])[-1][:200]
        raise ValueError("Não deu para baixar esse vídeo: " + erro)
    _, altura, dur = (linha.split("\t") + ["", ""])[:3]
    return {"arquivo": arq.name, "pasta": "Downloads/YouTube (na pasta do Octopus IA)", "tamanho_mb": round(arq.stat().st_size / 1e6, 1),
            "resolucao": (altura + "p") if altura.isdigit() else "", "segundos": int(float(dur)) if dur.replace(".", "").isdigit() else None}


def _executor_youtube(nome, args, cofre=None):
    if nome == "baixar_video":
        return json.dumps(baixar_video(args.get("link"), cofre), ensure_ascii=False)
    itens = buscar_youtube(args.get("termo"), args.get("quantidade"), args.get("tipo"))
    return json.dumps(itens, ensure_ascii=False) if itens else "A busca não trouxe vídeos para esse termo."


# ---------------- Personas (aba Criativos › Personas) ----------------
def _instrucoes_persona(cofre):
    skill = _sem_frontmatter((SKILLS / "persona" / "SKILL.md").read_text(encoding="utf-8"))
    modelo = (cofre / "Biblioteca" / "Modelos" / "Persona.md") if cofre else None
    return f"""Você é o agente Personas do Octopus IA. Responda sempre em português do Brasil.

{skill}

## Como você trabalha aqui dentro do Octopus IA
- Você não tem terminal nem internet. Os arquivos que você alcança são os da pasta do Octopus IA (regras mais abaixo). O material que o usuário anexa chega no texto da mensagem. O cofre você consulta pelas ferramentas.
- A oferta deste chat vem no contexto ("Oferta deste flow"): é só dela que você trata.
- Quando entregar as personas, a resposta é só o documento, começando pela linha `---`.

## Biblioteca/Modelos/Persona.md (o formato de cada persona)
{modelo.read_text(encoding="utf-8") if modelo and modelo.is_file() else "(use o formato da skill)"}
"""


def cerebro(v, expert, oferta):
    """Os números de cada pilar, para a aba Criativos › Cérebro: o que a biblioteca tem e o que a oferta já tem."""
    import controle, criativos
    conta = lambda pasta, tipo: len(_notas(v, pasta, tipo))
    out = {"biblioteca": {"narrativas": conta("Narrativas", "narrativa"), "formatos": conta("Formatos", "formato"), "angulos": conta("Ângulos", "angulo")},
           "expert": expert, "oferta": oferta, "da_oferta": None}
    base = pasta_oferta(v, expert, oferta)
    if base:
        n = lambda sub: len(list((base / sub).rglob("*.md"))) if (base / sub).is_dir() else 0
        out["da_oferta"] = {"big_ideas": n("Big ideas"), "anuncios": n("Anúncios"), "personas": len(criativos.personas(v, expert, oferta)),
                            "dicionario": (base / "Dicionário da oferta.md").is_file(), "auditoria": len(controle.anuncios(v, expert, oferta)),
                            "biblia": bool(list((base / "VSL").glob("Bíblia do nicho*.md"))), "tese": bool(list((base / "VSL").glob("Briefing de tese*.md"))),
                            "blocos": n("VSL/Blocos")}
    return out


# ---------------- Blocos de VSL (aba VSL) ----------------
def _briefings(cofre):
    if not cofre or not cofre.is_dir():
        return []
    return sorted(cofre.glob("Projetos/*/*/VSL/Briefing de tese*.md"), key=lambda p: p.stat().st_mtime, reverse=True)


def lista_briefings(cofre):
    out = []
    for p in _briefings(cofre):
        c = _campos(p.read_text(encoding="utf-8"))
        out.append({"caminho": p.relative_to(cofre).as_posix(),
                    "rotulo": " · ".join(x.strip('"') for x in [c.get("expert") or p.parts[-4], c.get("oferta") or p.parts[-3]] if x) + ("" if p.stem == "Briefing de tese" else f" ({p.stem[-1]})")})
    return out


CONTAR = _f("contar_caracteres", "Conta os caracteres e as palavras de um texto e estima o tempo de fala. Use para conferir o tamanho do bloco antes de entregar.", {"texto": {"type": "string"}}, ["texto"])
TRANSCREVER_YT = _f("transcrever_youtube", "Traz a transcrição de um vídeo do YouTube (pela legenda do vídeo; se não houver, baixa o áudio e transcreve no computador, o que demora alguns minutos). A transcrição entra como arquivo na lista VSLs de referência do nó Blocos de VSL e volta aqui para você ler.",
                    {"link": {"type": "string", "description": "o link do vídeo no YouTube"}}, ["link"])
INSTR_YT_BLOCOS = """
- **Trazer uma referência do YouTube:** `transcrever_youtube` devolve a transcrição do vídeo e a guarda na lista VSLs de referência do nó. Use quando faltar referência para um bloco ou o usuário pedir; diga qual vídeo trouxe."""


def _vtt_texto(vtt):
    """Legenda do YouTube → linhas "[mm:ss] fala", sem as repetições da legenda automática."""
    out, ultimo = [], ""
    for bloco in re.split(r"\n\s*\n", vtt):
        m = re.search(r"(\d+):(\d+):(\d+)\.\d+\s*-->", bloco)
        if not m:
            continue
        for l in bloco.splitlines():
            l = re.sub(r"<[^>]+>", "", l).strip()
            if not l or "-->" in l or l == ultimo:
                continue
            ultimo = l
            h, mi, sg = (int(x) for x in m.groups())
            out.append(f"[{h * 60 + mi:02d}:{sg:02d}] {l}")
    return "\n".join(out)


REDES = {"youtube": ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"),
         "tiktok": ("www.tiktok.com", "tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"),
         "instagram": ("www.instagram.com", "instagram.com")}
NOME_REDE = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}


def rede_do_link(link):
    """youtube | tiktok | instagram, ou erro se o link não for de uma das três."""
    import urllib.parse
    u = urllib.parse.urlparse(str(link or "").strip())
    for rede, hosts in REDES.items():
        if u.scheme == "https" and u.netloc.lower() in hosts and len(u.path) > 1:
            return rede
    raise ValueError("Cole o link de um vídeo do YouTube, do TikTok ou do Instagram (começando com https://).")


def _erro_rede(rede, stderr):
    ult = ((stderr or "").strip().splitlines() or ["motivo desconhecido"])[-1]
    if rede == "instagram" and re.search(r"login|logged|cookies|empty media|rate.?limit", ult, re.I):
        return "O Instagram não liberou este vídeo sem login. Ele costuma bloquear a leitura de fora; tente de novo mais tarde ou use o link do mesmo vídeo no TikTok ou no YouTube."
    if re.search(r"private|unavailable|removed|not exist|404", ult, re.I):
        return "Este vídeo não está disponível (privado, removido ou o link está errado)."
    return "Não deu para ler este link: " + re.sub(r"^ERROR:\s*(\[[^\]]*\]\s*)?[\w-]*:?\s*", "", ult)[:160]


def info_social(link):
    """O que dá para saber de um vídeo pelo link, sem API e sem login: título, autor, duração, visualizações e a miniatura (já embutida, porque o endereço dela expira)."""
    import base64, subprocess, urllib.request
    link = str(link or "").strip()
    rede = rede_do_link(link)
    if not Path(YTDLP[0]).exists():
        raise ValueError("O leitor de vídeos não está instalado no Octopus IA. Peça ao Claude Code ou ao Codex para rodar a instalação do Octopus IA de novo (instalar.py).")
    try:
        r = subprocess.run(YTDLP + ["--no-warnings", "--no-playlist", "--skip-download", "--socket-timeout", "20", "--dump-single-json", "--", link],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env_filho(), timeout=75)
        d = json.loads(r.stdout or "{}") if r.returncode == 0 else None
    except (subprocess.SubprocessError, ValueError, OSError):
        d, r = None, None
    if not d:
        raise ValueError(_erro_rede(rede, r.stderr if r else "a rede não respondeu a tempo"))
    thumb = ""
    # a miniatura fica embutida no nó (e vai no estado salvo): a de ~480 px é boa para o cartão e pesa pouco; as maiores só se não houver outra
    cands = [t for t in (d.get("thumbnails") or []) if isinstance(t, dict) and t.get("url")]
    cands.sort(key=lambda t: abs((t.get("width") or 480) - 480))
    capas = [t["url"] for t in cands] + [d.get("thumbnail")]
    for url in [c for c in dict.fromkeys(capas) if c][:4]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://" + REDES[rede][0] + "/"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                tipo, bruto = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0], resp.read(700_000)
            if tipo.startswith("image/") and 0 < len(bruto) < 250_000:
                thumb = f"data:{tipo};base64," + base64.b64encode(bruto).decode()
                break
        except Exception:
            continue
    dur = d.get("duration")
    return {"rede": rede, "rede_nome": NOME_REDE[rede], "link": link, "titulo": str(d.get("title") or d.get("description") or "")[:160].strip(),
            "autor": str(d.get("uploader") or d.get("channel") or d.get("uploader_id") or "")[:80], "segundos": int(dur) if isinstance(dur, (int, float)) else None,
            "visualizacoes": d.get("view_count"), "curtidas": d.get("like_count"), "legenda": str(d.get("description") or "")[:1500].strip(), "thumb": thumb,
            # vídeo em pé (Reels, TikTok, Shorts): o nó mostra a capa em pé também
            "vertical": bool(isinstance(d.get("width"), (int, float)) and isinstance(d.get("height"), (int, float)) and d["height"] > d["width"]) or (rede == "tiktok" and not d.get("width"))}


def transcrever_youtube(link, destino, qualquer_rede=False, progresso=lambda p: None):
    """Legenda do vídeo (rápido) ou, sem legenda, áudio + Whisper. Grava o .txt em `destino` e devolve (nome, texto).
    qualquer_rede: aceita também TikTok e Instagram (o nó Conteúdo das redes sociais)."""
    import subprocess, tempfile, urllib.parse
    link = str(link or "").strip()
    u = urllib.parse.urlparse(link)
    if qualquer_rede:
        rede_do_link(link)
    elif u.scheme != "https" or u.netloc.lower() not in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
        raise ValueError("Só dá para transcrever links do YouTube.")
    if not Path(YTDLP[0]).exists():
        raise ValueError("O YouTube e o Whisper não estão instalados no Octopus IA. Peça ao Claude Code ou ao Codex para rodar a instalação do Octopus IA de novo (instalar.py).")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        progresso(0.03)                                         # as etapas: procurar legenda (até 10%), baixar o áudio (até 25%), Whisper (o resto)
        r = subprocess.run(YTDLP + ["--no-warnings", "--no-playlist", "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "pt.*,es.*,en.*",
                                    "--sub-format", "vtt", "--print", "%(title)s\t%(duration)s", "--no-simulate", "-o", str(tmp / "v.%(ext)s"), "--", link],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env_filho(), timeout=180)
        info = next((l for l in (r.stdout or "").splitlines() if "\t" in l), "")
        titulo = info.split("\t")[0].strip() or "Vídeo"
        legendas = sorted(tmp.glob("v.*.vtt"), key=lambda p: (0 if ".pt" in p.name else 1 if ".es" in p.name else 2, "orig" not in p.name))
        texto = _vtt_texto(legendas[0].read_text(encoding="utf-8", errors="replace")) if legendas else ""
        como = "legenda do YouTube"
        if len(texto) < 200:                                   # sem legenda: baixa só o áudio e transcreve com o Whisper
            import transcricao
            progresso(0.1)
            r = subprocess.run(YTDLP + ["--no-warnings", "--no-playlist", "--max-filesize", "1G", "-f", "ba[ext=m4a]/ba/b", "-o", str(tmp / "audio.%(ext)s"), "--", link],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", env=env_filho(), timeout=900)
            audio = next(iter(tmp.glob("audio.*")), None)
            if r.returncode != 0 or not audio:
                raise ValueError("Esse vídeo não tem legenda e não deu para baixar o áudio: " + ((r.stderr or "").strip().splitlines() or ["motivo desconhecido"])[-1][:200])
            srt = tmp / "audio.srt"
            progresso(0.25)
            with transcricao.VEZ:                               # um Whisper por vez no computador: entra na mesma fila dos nós de Transcrição
                r = subprocess.Popen([str(transcricao.PY), str(transcricao.SCRIPT), str(audio), str(srt)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", env=env_filho(), bufsize=1)
                total = None
                for linha in r.stdout:                              # o Whisper avisa a duração e até onde já foi
                    try:
                        ev = json.loads(linha)
                    except ValueError:
                        continue
                    if "duracao" in ev:
                        total = ev["duracao"] or None
                    elif "t" in ev and total:
                        progresso(0.25 + 0.74 * min(1.0, ev["t"] / total))
                r.wait()
            if not srt.is_file():      # o Whisper às vezes fecha com erro depois de já ter gravado tudo: o que vale é a legenda existir
                raise ValueError("O Whisper não conseguiu transcrever esse vídeo.")
            texto, como = transcricao.texto_legivel(srt.read_text(encoding="utf-8")), "Whisper"
        destino.mkdir(parents=True, exist_ok=True)
        base = (NOME_REDE[rede_do_link(link)] if qualquer_rede else "YouTube") + " - " + re.sub(r'[/\\:*?"<>|#^\[\]]', " ", titulo)[:90].strip()
        alvo, i = destino / f"{base}.txt", 2
        while alvo.exists():
            alvo = destino / f"{base} ({i}).txt"; i += 1
        alvo.write_text(f"Vídeo: {titulo}\nLink: {link}\nTranscrição: {como}\n\n{texto}\n", encoding="utf-8")
        return alvo.name, alvo.read_text(encoding="utf-8")


def _instrucoes_blocos(cofre):
    skill = _sem_frontmatter((SKILLS / "blocos-de-vsl" / "SKILL.md").read_text(encoding="utf-8"))
    le = lambda p: p.read_text(encoding="utf-8") if p.is_file() else "(não encontrado)"
    return f"""Você é o agente Blocos de VSL do Octopus IA. Responda sempre em português do Brasil.

{skill}

## Como você trabalha aqui dentro do Octopus IA
- Você não tem terminal nem internet. Os arquivos que você alcança são os da pasta do Octopus IA (regras mais abaixo). O Briefing de tese, as bíblias e as VSLs de referência chegam no texto da mensagem, marcados como contexto. As transcrições ligadas também valem para a ferramenta `medir_blocos` (use o nome do arquivo como `anexo`).
- Um bloco por resposta. A resposta com o bloco é só o documento, começando pela linha `---`.

## Biblioteca/Vícios de IA (nota do cofre)
{le(cofre / "Biblioteca" / "Vícios de IA.md") if cofre else "(sem cofre)"}
"""


def _executor_blocos(pasta, cofre):
    medir = _executor_biblia(pasta, cofre)

    def executar(nome, args):
        if nome == "medir_blocos":
            return medir(nome, args)
        if nome == "contar_caracteres":
            t = str(args.get("texto") or "").strip()
            pal = len(t.split())
            return json.dumps({"caracteres": len(t), "palavras": pal, "tempo_estimado": _tempo(pal)}, ensure_ascii=False)
        if nome == "transcrever_youtube":
            try:
                no = json.loads((pasta / "blocos.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                no = None                                   # sem o nó VSLs de referência ligado: a transcrição vem só para a conversa
            arq, texto = transcrever_youtube(args.get("link"), Path(no["pasta"]) if no else pasta / "youtube")
            (pasta / "anexos").mkdir(parents=True, exist_ok=True)
            (pasta / "anexos" / arq).write_text(texto, encoding="utf-8")
            if not no:
                return f"Transcrição pronta ({len(texto)} caracteres). Não há nó VSLs de referência ligado ao Blocos de VSL, então ela fica só nesta conversa.\n\n{texto[:120000]}"
            novos = pasta / "novos.json"
            lista = json.loads(novos.read_text(encoding="utf-8")) if novos.is_file() else []
            lista.append({"no": no["no"], "nome": arq, "caracteres": len(texto)})
            novos.write_text(json.dumps(lista, ensure_ascii=False), encoding="utf-8")
            return f"Transcrição guardada como \"{arq}\" nas VSLs de referência do nó ({len(texto)} caracteres).\n\n{texto[:120000]}"
        raise ValueError("ferramenta desconhecida")
    return executar


# ---------------- Chat livre ----------------
# ---------------- o cofre, para todos os chats ----------------
FERR_COFRE = [
    _f("listar_cofre", "Mostra os experts e as ofertas do Cérebro (Projetos/{Expert}/{Oferta}) e o que cada oferta já tem: bíblia do nicho, briefing de tese, anúncios, big ideas, controle de mercado."),
    _f("salvar_no_cerebro", "Grava no cofre o último documento entregue neste chat (bíblia do nicho, briefing de tese, VSL da oferta, anúncios, big ideas, controle de mercado, bloco de VSL, dicionário da oferta ou personas), dentro da oferta indicada. Só chame quando o usuário pedir para gravar e o expert e a oferta estiverem claros.",
       {"expert": {"type": "string"}, "oferta": {"type": "string"},
        "criar": {"type": "boolean", "description": "true só depois de o usuário confirmar que quer criar um expert ou uma oferta que ainda não existe"},
        "substituir": {"type": "boolean", "description": "true só se o usuário pediu para substituir a bíblia ou o briefing que já existe na oferta"}}, ["expert", "oferta"]),
    _f("dividir_vsl", "Divide uma VSL em blocos sem reescrever o texto: põe o título de cada bloco no ponto em que ele começa. Dois usos: (1) a VSL da oferta que já está no Cérebro: informe `caminho` e os títulos entram na nota dela; (2) uma VSL que o usuário mandou no chat: informe `anexo` e o PRÓPRIO ARQUIVO do chat é editado, ganhando os títulos (o usuário abre o arquivo e já vê os blocos). Se ele também quiser guardar essa VSL de referência na oferta, informe `expert`, `oferta` e `nome`: uma cópia vai para VSL/Referências.",
       {"caminho": {"type": "string", "description": "a nota da VSL no Cérebro, como veio de listar_notas (ex.: Projetos/Fulano/Oferta X/VSL/VSL V1.md)"},
        "anexo": {"type": "string", "description": "nome do arquivo ou do texto colado com a VSL, quando ela veio no chat"},
        "expert": {"type": "string"}, "oferta": {"type": "string"},
        "nome": {"type": "string", "description": "nome para a VSL de referência (ex.: o produto ou o concorrente)"},
        "blocos": {"type": "array", "description": "os blocos, na ordem",
                   "items": {"type": "object", "properties": {"bloco": {"type": "string", "description": "nome curto do bloco"},
                             "inicio": {"type": "string", "description": "as primeiras 6 a 10 palavras do bloco, copiadas exatamente do texto"}}, "required": ["bloco", "inicio"]}}}, ["blocos"]),
    _f("criar_oferta", "Cria no Cérebro um expert (com as notas Credenciais e História, a partir dos modelos) e, se informada, uma oferta dele já com as pastas padrão (VSL, Anúncios, Big ideas, Controle de mercado, Personas). Só depois de o usuário confirmar. Se já existe, não muda nada.",
       {"expert": {"type": "string"}, "oferta": {"type": "string", "description": "opcional: sem ela, cria só o expert"},
        "confirmado": {"type": "boolean", "description": "true só depois do sim do usuário"}}, ["expert"]),
    _f("cadastrar_vsl", "Guarda no Cérebro a VSL que o usuário mandou (o script pronto), como a VSL de uma oferta: Projetos/{Expert}/{Oferta}/VSL/VSL V{n}.md. O Octopus IA pega o TEXTO DO ARQUIVO que o usuário enviou e grava como está: você NÃO reescreve a VSL, só informa os dados e, se quiser dividir em blocos, onde cada bloco começa.",
       {"anexo": {"type": "string", "description": "nome do arquivo ou do texto colado com a VSL, como aparece na conversa (ex.: \"Texto colado 1\"). Pode omitir se a conversa só tem um"},
        "expert": {"type": "string"}, "oferta": {"type": "string"},
        "versao": {"type": "string", "description": "V1, V2… a que o usuário disse"},
        "nome": {"type": "string", "description": "nome da VSL; sem o usuário dizer, o nome da oferta"},
        "nicho": {"type": "string"}, "data": {"type": "string", "description": "AAAA-MM-DD em que a VSL foi feita, só se o usuário informou"},
        "link": {"type": "string", "description": "link da VSL (Drive ou página), só se o usuário informou"},
        "play_rate": {"type": "number"}, "retencao_1min": {"type": "number"}, "retencao_pitch": {"type": "number"}, "conversao": {"type": "number"},
        "blocos": {"type": "array", "description": "opcional: os blocos da VSL, na ordem. O Octopus IA põe o título de cada bloco no ponto certo do texto, sem mudar nenhuma palavra",
                   "items": {"type": "object", "properties": {"bloco": {"type": "string", "description": "nome curto do bloco"},
                             "inicio": {"type": "string", "description": "as primeiras 6 a 10 palavras do bloco, copiadas exatamente do texto"}}, "required": ["bloco", "inicio"]}},
        "criar": {"type": "boolean", "description": "true só depois de o usuário confirmar a criação de um expert ou de uma oferta que ainda não existe"},
        "substituir": {"type": "boolean", "description": "true só se o usuário pediu para trocar a VSL dessa versão que já existe"}}, ["expert", "oferta", "versao"]),
]
FERR_COFRE_LER = [
    _f("listar_notas", "Lista as notas (.md) de uma pasta do cofre, com as subpastas. Ex.: Projetos/Fulano/Oferta X, Biblioteca/Narrativas, Swipe/Spy.", {"pasta": {"type": "string"}}, ["pasta"]),
    _f("ler_nota", "Lê uma nota do cofre. Use o caminho como veio de listar_notas.", {"caminho": {"type": "string"}}, ["caminho"]),
    _f("consultar_notas", "Consulta o Cérebro pelas propriedades das notas, como numa tabela: filtra por tipo, pasta, valor de propriedade e texto, e devolve as propriedades de cada nota. Use quando precisar de uma lista com critério (ex.: anúncios com a narrativa X, ângulos de CTA para anúncio, personas de uma oferta, anúncios validados).",
       {"tipo": {"type": "string", "description": "anuncio | vsl | big_idea | narrativa | formato | angulo | persona | controle_anuncio | bloco_de_vsl | biblia-do-nicho | briefing-de-tese | dicionario_da_oferta"},
        "pasta": {"type": "string", "description": "começo do caminho, ex.: Projetos/Fulano/Oferta X"},
        "onde": {"type": "object", "description": "propriedade → valor, ex.: {\"narrativa\": \"01 O Erro Terrível\", \"status\": \"validado\"}"},
        "texto": {"type": "string", "description": "trecho que precisa aparecer na nota"},
        "limite": {"type": "integer"}}),
]
INSTR_COFRE = """## O Cérebro (a pasta de arquivos)
Este chat enxerga o Cérebro, a pasta de arquivos do Octopus IA. A hierarquia é sempre a mesma:

    Projetos/{Expert}/{Oferta}/VSL/Bíblia do nicho.md
    Projetos/{Expert}/{Oferta}/VSL/Briefing de tese.md
    Projetos/{Expert}/{Oferta}/VSL/VSL V1.md   (a VSL da oferta, uma nota por versão; os anúncios se ligam a ela pela propriedade vsl)
    Projetos/{Expert}/{Oferta}/Anúncios/Remessa NN/AD NN - título.md
    Projetos/{Expert}/{Oferta}/Big ideas/
    Projetos/{Expert}/{Oferta}/Controle de mercado/
    Biblioteca/ (modelos, narrativas, formatos) · Swipe/Spy/ (bibliotecas de anúncios monitoradas)

Tudo o que é produzido fica dentro de um expert e de uma oferta. Nada é gravado solto.

**Tudo parte de um modelo.** Cada tipo de documento tem a sua ficha em Biblioteca/Modelos/ (Bíblia do nicho, Briefing de tese, Anúncio, Big idea, Persona, Dicionário da oferta, Anúncio do controle de mercado, Narrativa, Formato, Ângulo, Spy página, Relatório de Spy, Credenciais, História). Nada é criado fora de um modelo. Se o usuário pedir um documento que ainda não tem modelo, avise e proponha criar o modelo antes.

**O expert** tem duas notas que valem para todas as ofertas dele: Projetos/{Expert}/Credenciais.md e Projetos/{Expert}/História.md. Leia as duas quando precisar de autoridade, prova ou da história do expert.

**Gravar pelo chat.** Não existe botão de salvar na tela: tudo é guardado pelo pedido do usuário no chat ("coloca na oferta X", "salva no Cérebro"). Nunca diga para ele clicar em Salvar no Cérebro (se outra instrução citar esse botão, ignore: ele foi retirado). Depois de entregar um documento que ainda não foi guardado, pergunte em uma linha se ele quer salvar e em qual oferta. Quando ele pedir:
1. O documento pode já ter sido entregue numa resposta anterior, ou sair nesta mesma resposta. **Se o usuário mandou o material e já pediu para salvar ("salva no controle de mercado", "já grava na oferta X"), faça tudo de uma vez:** descubra o destino (passos 2 a 4), chame `salvar_no_cerebro` e termine a resposta com o documento, só ele, começando pela linha `---`. O Octopus IA grava quando o documento chega. Não escreva o documento no meio da resposta nem duas vezes.
2. Descubra o expert e a oferta: o que o usuário disse, ou o nó Oferta ligado ao chat. Chame `listar_cofre` para achar o nome exato (o usuário pode falar só um pedaço do nome).
3. **Se ele não disse a oferta (ou o expert) e não há nó Oferta, pergunte**, mostrando as opções que existem no cofre. Não adivinhe e não escolha por ele. Se só existe um expert com uma oferta, confirme em uma linha.
4. Se a oferta ou o expert não existem, pergunte se é para criar; só com o sim chame com `criar: true`.
5. Chame `salvar_no_cerebro`. O Octopus IA grava em seguida, na pasta certa para o tipo do documento. Responda em uma frase onde vai ficar. **Não escreva o documento de novo.**
{leitura}

**Guardar a VSL de uma oferta.** Quando o usuário mandar a VSL dele (o script pronto, colado, anexado ou ligado no flow) para guardar, cadastrar ou salvar numa oferta, com ou sem `#salvar-vsl`, use a ferramenta `cadastrar_vsl`. Ela pega o texto do arquivo que ele mandou e grava como está, no modelo de VSL.
- **Você não reescreve a VSL.** Não copie o script na resposta nem na ferramenta: informe só os dados (expert, oferta, versão, nome, nicho, e link, data e métricas se ele informou; nunca invente) e, em `anexo`, o nome do arquivo ou do texto colado.
- **Blocos:** se quiser dividir, mande em `blocos` o nome de cada bloco e as primeiras 6 a 10 palavras dele, copiadas do texto, na ordem. O Octopus IA põe os títulos no lugar. Se o script já veio com blocos marcados, use os dele. Se a ferramenta disser que não achou o começo de um bloco, corrija as palavras e chame de novo. Sem `blocos`, a VSL é gravada inteira, sem divisão.
- Sem o usuário dizer a versão, pergunte. Se o expert ou a oferta não existem, a ferramenta avisa: pergunte se é para criar e só então chame com `criar: true`.
- Depois de gravar, responda em uma ou duas frases dizendo onde ficou.
- **Dividir uma VSL em blocos** (o usuário colou ou anexou uma VSL e pediu para dividir, ou a VSL já está no Cérebro): use `dividir_vsl`, com o nome de cada bloco e as primeiras palavras dele. **Nunca reescreva a VSL na resposta para mostrar os blocos**: a ferramenta edita o próprio arquivo (o do chat ou a nota do Cérebro), e é nele que o usuário vê os blocos. Na resposta vai só a lista dos blocos. A função `#dividir-vsl` traz o passo a passo.

**Todo chat enxerga o Cérebro inteiro.** Seja de VSL, de Criativos ou qualquer outro, com ou sem nó Oferta, você pode consultar tudo o que está na pasta do Octopus IA: todos os experts (Credenciais e História), todas as ofertas, as VSLs, os anúncios, as personas, o controle de mercado, a Biblioteca e o Spy. Use isso sempre que ajudar o pedido.

**Com o nó Oferta ligado**, o que muda é só onde este chat grava e altera: os documentos novos vão para Projetos/{Expert}/{Oferta} do nó, e as alterações valem para as notas dessa oferta e do expert dela. Se o usuário pedir para gravar ou alterar algo de outra oferta, diga que este chat está ligado à oferta do nó e que é só trocar a oferta no nó ou usar outro chat. Ler, pode qualquer uma."""
INSTR_COFRE_LER = """
**Consultar por critério.** `consultar_notas` funciona como uma tabela das notas: filtra por tipo, pasta e propriedade (ex.: tipo `anuncio`, onde `{"narrativa": "01 O Erro Terrível"}`). Use em vez de abrir nota por nota quando a pergunta for "quais", "quantos" ou "todos os que".

**Consultar o cofre.** Quando o usuário pedir algo que está no cofre (a bíblia de uma oferta, a tese, um anúncio, uma biblioteca do Spy), use `listar_cofre`, `listar_notas` e `ler_nota`. Diga de qual nota veio. Se ele não disser de qual oferta, pergunte."""
INSTR_COFRE_SEM_LER = """
**Neste chat, o documento é feito só com o material que o usuário mandou.** Você pode consultar o Cérebro quando ele perguntar algo que está lá, mas não use notas do Cérebro para preencher o documento."""


def cortar_em_blocos(texto, blocos):
    """Põe o título de cada bloco ("### 1. Nome") no ponto em que o trecho começa, sem mudar o texto.
    blocos: [{bloco, inicio}] com as primeiras palavras de cada um, na ordem. Devolve (texto dividido, quantos blocos, [os que não achou])."""
    cortes, pos, nao_achei = [], 0, []
    for b in blocos or []:
        nomeb, ini = limpar_txt(b.get("bloco")), str(b.get("inicio") or "").strip()
        palavras = re.findall(r"\w+", ini)[:8]
        m = re.compile(r"\W+".join(re.escape(w) for w in palavras), re.I).search(texto, pos) if len(palavras) >= 3 else None
        if not m or not nomeb:
            nao_achei.append(nomeb or ini[:40])
            continue
        cortes.append((m.start(), nomeb))
        pos = m.end()
    if nao_achei or not cortes:
        return texto, 0, nao_achei
    if cortes[0][0] > 0 and texto[:cortes[0][0]].strip():
        cortes.insert(0, (0, "Abertura"))
    partes = []
    for k, (ini_frase, nomeb) in enumerate(cortes):
        fim = cortes[k + 1][0] if k + 1 < len(cortes) else len(texto)
        partes.append(f"### {k + 1}. {nomeb}\n\n{texto[ini_frase:fim].strip()}")
    return "\n\n".join(partes), len(cortes), []


def limpar_txt(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()[:80]


def _nome_ok(x):
    x = re.sub(r"\s+", " ", str(x or "")).strip()
    from locais import nome_windows
    x = nome_windows(x[:80]) if x else x
    return x if x and not x.startswith(".") and not re.search(r'[/\\:*?"<>|]', x) else None


def _arvore_cofre(cofre):
    out = []
    base = cofre / "Projetos"
    ok = lambda p: p.is_dir() and not p.name.startswith(".")
    for e in sorted(p for p in base.iterdir() if ok(p)) if base.is_dir() else []:
        ofs = []
        for o in sorted(p for p in e.iterdir() if ok(p) and p.name != "Atlas"):
            n = lambda sub: len(list((o / sub).rglob("*.md"))) if (o / sub).is_dir() else 0
            ofs.append({"oferta": o.name, "biblia_do_nicho": bool(list((o / "VSL").glob("Bíblia do nicho*.md"))), "briefing_de_tese": bool(list((o / "VSL").glob("Briefing de tese*.md"))),
                        "anuncios": n("Anúncios"), "big_ideas": n("Big ideas"), "controle_de_mercado": n("Controle de mercado/Anúncios")})
        out.append({"expert": e.name, "ofertas": ofs})
    return out


def _dentro_cofre(cofre, rel):
    rel = str(rel or "").strip().strip("/")
    if not rel or any(x.startswith(".") or x.casefold() == "atlas" for x in Path(rel).parts):     # casefold: Mac e Windows não distinguem "atlas" de "Atlas"
        return None
    p = (cofre / rel)
    try:
        p.resolve().relative_to(cofre.resolve())
    except ValueError:
        return None
    return p


def _executor_cofre(pasta, cofre):
    def presa():
        """Com o nó Oferta ligado, o chat só enxerga aquela oferta (e a Biblioteca, com os modelos)."""
        try:
            o = json.loads((pasta / "oferta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return (o["expert"], o["oferta"]) if pasta_oferta(cofre, o.get("expert"), o.get("oferta")) else None

    def liberado(p, of):
        if not of:
            return True
        for raiz in (cofre / "Projetos" / of[0] / of[1], cofre / "Biblioteca"):
            try:
                p.resolve().relative_to(raiz.resolve())
                return True
            except ValueError:
                pass
        return False

    def executar(nome, args):
        if not cofre or not cofre.is_dir():
            return "A pasta de arquivos do Octopus IA (o Cérebro) não foi encontrada neste computador. Peça para o usuário reabrir o Octopus IA."
        of = presa()
        # o nó Oferta define ONDE este chat grava e altera. Para LER, todo chat enxerga o Cérebro inteiro
        fora = (f"Este chat está ligado à oferta {of[1]} ({of[0]}) pelo nó Oferta: ele lê o Cérebro inteiro, mas só grava e altera em Projetos/{of[0]}/{of[1]}/ (e nas notas do expert). "
                "Para gravar em outra oferta, o usuário troca a oferta no nó ou usa outro chat.") if of else ""
        if nome == "listar_cofre":
            a = _arvore_cofre(cofre)
            return json.dumps(a, ensure_ascii=False) if a else "O cofre ainda não tem nenhum expert em Projetos/."
        if nome == "listar_notas":
            p = _dentro_cofre(cofre, args.get("pasta"))
            if not p or not p.is_dir():
                raise ValueError("pasta não encontrada no cofre")
            itens = [x.relative_to(cofre).as_posix() for x in sorted(p.rglob("*.md"))
                     if not any(y.startswith(".") or y == "Atlas" for y in x.relative_to(cofre).parts)]
            return json.dumps({"notas": itens[:300], "total": len(itens)}, ensure_ascii=False) if itens else "Pasta sem notas."
        if nome == "consultar_notas":
            import indice
            base = None
            onde = args.get("onde") if isinstance(args.get("onde"), dict) else None
            r = indice.consultar(cofre, args.get("tipo"), args.get("pasta"), onde, args.get("texto"), args.get("limite") or 60, base)
            return json.dumps(r, ensure_ascii=False) if r["total"] else "Nenhuma nota com esse critério."
        if nome == "ler_nota":
            p = _dentro_cofre(cofre, args.get("caminho"))
            if p and not p.suffix:
                p = p.with_suffix(".md")
            if not p or p.suffix.lower() != ".md" or not p.is_file():
                raise ValueError("nota não encontrada. Use um caminho de listar_notas.")
            return p.read_text(encoding="utf-8", errors="replace")[:60000]
        if nome == "dividir_vsl":
            blocos = args.get("blocos")
            if not isinstance(blocos, list) or not blocos:
                return "Informe os blocos: o nome de cada um e as primeiras palavras dele."
            sem_titulos = lambda t: re.sub(r"\n{3,}", "\n\n", re.sub(r"^### \d+\. [^\n]*\n?", "", t, flags=re.M)).strip()      # só os títulos de bloco que o próprio app pôs ("### 3. Lead"); o resto do texto fica
            if args.get("caminho"):                     # a VSL da oferta, já no Cérebro: os títulos entram na nota
                p = _dentro_cofre(cofre, args["caminho"])
                if p and not p.suffix:
                    p = p.with_suffix(".md")
                if not p or not p.is_file() or p.suffix.lower() != ".md":
                    return "Nota não encontrada. Use o caminho como veio de listar_notas."
                if not liberado(p, of):
                    return fora
                if p.relative_to(cofre).parts[0].casefold() != "projetos":      # só VSLs em Projetos/: a Biblioteca e o Swipe não são divididos
                    return "dividir_vsl só divide uma VSL guardada em Projetos/ (a VSL da oferta ou uma VSL de referência). Essa nota não é uma VSL de oferta."
                if (MODELO_BASE / p.relative_to(cofre)).exists():
                    return "Essa é uma nota de base do Octopus IA e não é alterada."
                atual = p.read_text(encoding="utf-8", errors="replace")
                m = re.search(r"^## Script[ \t]*\n", atual, re.M)
                cab, corpo = (atual[:m.end()], atual[m.end():]) if m else (re.match(r"(?:---\n.*?\n---\n)?(?:\s*# [^\n]*\n)?", atual, re.S).group(0), None)
                if corpo is None:
                    corpo = atual[len(cab):]
                texto = sem_titulos(corpo)
                script, n_blocos, nao_achei = cortar_em_blocos(texto, blocos)
                if nao_achei:
                    return ("Não achei no texto o começo destes blocos: " + "; ".join(nao_achei) + ". Copie as primeiras palavras exatamente como estão na nota "
                            "(na ordem em que aparecem) e chame de novo. Nada foi mudado.")
                lixo = cofre / ".trash"
                lixo.mkdir(exist_ok=True)
                shutil.copy2(p, lixo / f"{p.stem} (antes de dividir {time.strftime('%Y-%m-%d %Hh%Mm%S')}){p.suffix}")
                p.write_text(cab.rstrip("\n") + "\n\n" + script + "\n", encoding="utf-8")
                return (f"{p.relative_to(cofre).as_posix()} dividida em {n_blocos} blocos, sem mudar o texto. A versão anterior está na lixeira. "
                        "Responda com a lista dos blocos (nome e uma linha sobre o que cada um faz). NÃO escreva a VSL na resposta.")
            # a VSL veio no chat: o próprio arquivo do chat ganha os títulos dos blocos (e, se pedirem, uma cópia vai para a oferta)
            arqs = sorted((pasta / "anexos").glob("*")) if (pasta / "anexos").is_dir() else []
            try:
                arq = (pasta / "anexos" / nome_anexo(args["anexo"])) if args.get("anexo") else (arqs[0] if len(arqs) == 1 else None)
            except ValueError:
                arq = None
            if not arq or not arq.is_file():
                return "Diga qual arquivo é a VSL (anexo). Arquivos desta conversa: " + (", ".join(x.name for x in arqs) or "nenhum") + "."
            texto = arq.read_text(encoding="utf-8", errors="replace")
            if "-->" in texto:
                texto = "\n".join(l.strip() for l in texto.splitlines() if l.strip() and "-->" not in l and not l.strip().isdigit() and l.strip() != "WEBVTT")
            script, n_blocos, nao_achei = cortar_em_blocos(sem_titulos(texto), blocos)
            if nao_achei:
                return ("Não achei no texto o começo destes blocos: " + "; ".join(nao_achei) + ". Copie as primeiras palavras exatamente como estão no arquivo "
                        "(na ordem em que aparecem) e chame de novo. Nada foi mudado.")
            arq.write_text(script + "\n", encoding="utf-8")
            reg = pasta / "anexos_editados.json"
            try:
                lista = json.loads(reg.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                lista = []
            reg.write_text(json.dumps([x for x in lista if x.get("arquivo") != arq.name] + [{"arquivo": arq.name, "texto": script}], ensure_ascii=False), encoding="utf-8")
            feito = f"O arquivo {arq.name} desta conversa foi dividido em {n_blocos} blocos, sem mudar o texto: ao abrir o arquivo no chat, o usuário já vê os blocos. "
            expert, oferta = _nome_ok(args.get("expert")), _nome_ok(args.get("oferta"))
            if not of and not (expert and oferta):
                return feito + "Responda com a lista dos blocos (nome e uma linha sobre o que cada um faz). NÃO escreva a VSL na resposta."
            if of and not args.get("nome") and not (args.get("expert") or args.get("oferta")):
                return feito + "Responda com a lista dos blocos (nome e uma linha sobre o que cada um faz). NÃO escreva a VSL na resposta."
            if of:
                expert, oferta = of
            elif expert and oferta:                     # o nome como está na pasta (o usuário pode ter escrito sem maiúscula ou sem acento)
                igual = lambda x, y: _sem_acento(x).lower() == _sem_acento(y).lower()
                e = next((x for x in _arvore_cofre(cofre) if igual(x["expert"], expert)), None)
                o = next((x for x in e["ofertas"] if igual(x["oferta"], oferta)), None) if e else None
                expert, oferta = (e["expert"], o["oferta"]) if o else (None, None)
            base_of = pasta_oferta(cofre, expert, oferta) if expert and oferta else None
            if not base_of:
                return feito + "A cópia na oferta não foi gravada: a oferta informada não existe (use listar_cofre). Responda com a lista dos blocos."
            titulo = _nome_ok(args.get("nome")) or _nome_ok(Path(arq.name).stem) or "VSL de referência"
            destino = Path(base_of) / "VSL" / "Referências"
            destino.mkdir(parents=True, exist_ok=True)
            alvo, k = destino / f"{titulo}.md", 2
            while alvo.exists():
                alvo = destino / f"{titulo} ({k}).md"; k += 1
            alvo.write_text(f'---\ntipo: "vsl_referencia"\nnome: {json.dumps(titulo, ensure_ascii=False)}\nexpert: {json.dumps(Path(base_of).parent.name, ensure_ascii=False)}\n'
                            f'oferta: {json.dumps(Path(base_of).name, ensure_ascii=False)}\ndata: "{time.strftime("%Y-%m-%d")}"\n---\n# {titulo}\n\n## Script\n\n{script}\n', encoding="utf-8")
            return (feito + f"Uma cópia ficou guardada em {alvo.relative_to(cofre).as_posix()}. "
                    "Responda com a lista dos blocos (nome e uma linha sobre o que cada um faz). NÃO escreva a VSL na resposta.")
        if nome == "criar_oferta":
            import indice
            expert, oferta = _nome_ok(args.get("expert")), (_nome_ok(args.get("oferta")) if args.get("oferta") else "")
            if of:
                return fora
            if not expert or (args.get("oferta") and not oferta):
                return 'Nome inválido (vazio ou com / \\ : * ? " < > |). Pergunte ao usuário.'
            arv = _arvore_cofre(cofre)
            acha = lambda lista, chave, alvo: next((x for x in lista if _sem_acento(x[chave]).lower() == _sem_acento(alvo).lower()), None)
            e = acha(arv, "expert", expert)
            o = acha(e["ofertas"], "oferta", oferta) if e and oferta else None
            if e and (not oferta or o):
                return f"Já existe: Projetos/{e['expert']}" + (f"/{o['oferta']}" if o else "") + ". Nada foi mudado; pode seguir."
            if not args.get("confirmado"):
                return "Ainda não foi criado. Diga ao usuário, em uma frase, o que vai ser criado e só chame de novo com confirmado: true depois do sim."
            expert = e["expert"] if e else expert
            (cofre / "Projetos" / expert).mkdir(parents=True, exist_ok=True)
            indice.ficha_do_expert(cofre, expert)
            if oferta:
                for sub_ in ("VSL", "Anúncios", "Big ideas", "Controle de mercado", "Personas"):
                    (cofre / "Projetos" / expert / oferta / sub_).mkdir(parents=True, exist_ok=True)
            return (f"Criado: Projetos/{expert}" + (f"/{oferta}, com as pastas padrão (VSL, Criativos, Big ideas, Mapa do mercado)" if oferta else "")
                    + (". O expert já tem as notas Credenciais e História, do modelo, para preencher." if not e else "."))
        if nome == "cadastrar_vsl":
            import criativos
            expert, oferta = _nome_ok(args.get("expert")), _nome_ok(args.get("oferta"))
            if of:
                mesmo = lambda x, y: not x or _sem_acento(x).lower() == _sem_acento(y).lower()
                if not mesmo(expert, of[0]) or not mesmo(oferta, of[1]):
                    return fora
                expert, oferta = of
            versao = criativos.versao_vsl(args.get("versao"))
            if not expert or not oferta or not versao:
                return "Falta o expert, a oferta ou a versão (V1, V2…). Pergunte ao usuário o que faltar."
            arv = _arvore_cofre(cofre)
            acha = lambda lista, chave, alvo: next((x for x in lista if _sem_acento(x[chave]).lower() == _sem_acento(alvo).lower()), None)
            e = acha(arv, "expert", expert)
            o = acha(e["ofertas"], "oferta", oferta) if e else None
            if (not e or not o) and not args.get("criar"):
                return json.dumps({"gravado": False, "motivo": ("o expert não existe no Cérebro" if not e else "a oferta não existe neste expert"),
                                   "existe": [{"expert": x["expert"], "ofertas": [y["oferta"] for y in x["ofertas"]]} for x in arv],
                                   "o_que_fazer": "Pergunte ao usuário se é uma dessas ou se é para criar. Só chame de novo com criar: true depois do sim."}, ensure_ascii=False)
            expert, oferta = (e["expert"] if e else expert), (o["oferta"] if o else oferta)
            nova_oferta, novo_expert = not o, not e
            if (cofre / "Projetos" / expert / oferta / "VSL" / f"VSL {versao}.md").exists() and not args.get("substituir"):
                return f"A oferta já tem a VSL {versao}. Pergunte ao usuário se é para trocar essa (aí chame com substituir: true) ou se esta é outra versão."
            arqs = sorted((pasta / "anexos").glob("*")) if (pasta / "anexos").is_dir() else []
            if args.get("anexo"):
                try:
                    arq = pasta / "anexos" / nome_anexo(args["anexo"])
                except ValueError:
                    arq = None
                if not arq or not arq.is_file():
                    return "Anexo não encontrado. Arquivos desta conversa: " + (", ".join(p.name for p in arqs) or "nenhum") + "."
            elif len(arqs) == 1:
                arq = arqs[0]
            else:
                return ("Diga qual arquivo é a VSL (anexo). Arquivos desta conversa: " + ", ".join(p.name for p in arqs) + "." if arqs
                        else "Não há arquivo com a VSL nesta conversa. Peça para o usuário colar o script ou anexar o arquivo.")
            texto = arq.read_text(encoding="utf-8", errors="replace")
            if "-->" in texto:                          # legenda: fica só a fala
                texto = "\n".join(l.strip() for l in texto.splitlines() if l.strip() and "-->" not in l and not l.strip().isdigit() and l.strip() != "WEBVTT")
            texto = texto.strip()
            if len(texto) < 200:
                return "O arquivo está vazio ou curto demais para ser uma VSL."
            script, n_blocos, nao_achei = cortar_em_blocos(texto, args.get("blocos"))
            if nao_achei:
                return ("Não achei no texto o começo destes blocos: " + "; ".join(nao_achei) + ". Copie as primeiras palavras exatamente como estão no arquivo "
                        "(na ordem em que aparecem) e chame de novo. Nada foi gravado.")
            cortes = [None] * n_blocos
            campos = {"tipo": "vsl-da-oferta", "nome": limpar_txt(args.get("nome")) or oferta, "versao": versao}
            for k in ("nicho", "data", "link", "play_rate", "retencao_1min", "retencao_pitch", "conversao"):
                if args.get(k) not in (None, ""):
                    campos[k] = args[k]
            doc = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in campos.items()) + f"\n---\n# VSL {versao}\n\n## Script\n\n{script}\n"
            try:
                r = criativos.gravar_vsl(cofre, expert, oferta, doc)
            except criativos.ErroCriativos as err:
                return f"Não foi gravado: {err}"
            if nova_oferta:                             # oferta nova nasce com as pastas padrão
                for sub in ("VSL", "Anúncios", "Big ideas", "Controle de mercado", "Personas"):
                    (cofre / "Projetos" / expert / oferta / sub).mkdir(parents=True, exist_ok=True)
            if novo_expert:
                import indice
                indice.ficha_do_expert(cofre, expert)
            tam = f"{len(texto):,}".replace(",", ".")
            return (f"VSL {versao} gravada em {r['caminho']}, com o texto do arquivo {arq.name} inteiro ({tam} caracteres"
                    + (f", dividida em {len(cortes)} blocos" if cortes else ", sem divisão em blocos") + "). "
                    + (f"A oferta {oferta} foi criada com as pastas padrão (VSL, Criativos, Big ideas, Mapa do mercado). " if nova_oferta else "")
                    + "Diga isso ao usuário em uma ou duas frases. NÃO escreva a VSL na resposta.")
        if nome == "salvar_no_cerebro":
            try:
                doc = json.loads((pasta / "doc.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                doc = None
            # sem documento de uma resposta anterior: o documento ainda vai sair NESTA resposta. O destino fica registrado e o Octopus IA grava quando ele chegar
            falta_doc = not doc or not doc.get("tipo")
            expert, oferta = _nome_ok(args.get("expert")), _nome_ok(args.get("oferta"))
            if of:
                mesmo = lambda x, y: not x or _sem_acento(x).lower() == _sem_acento(y).lower()
                if not mesmo(expert, of[0]) or not mesmo(oferta, of[1]):
                    return fora
                expert, oferta = of
            if not expert or not oferta:
                return "Falta o expert ou a oferta (ou o nome tem caractere que não pode: / \\ : * ? \" < > |). Pergunte ao usuário."
            arv = _arvore_cofre(cofre)
            acha = lambda lista, chave, alvo: next((x for x in lista if _sem_acento(x[chave]).lower() == _sem_acento(alvo).lower()), None)
            e = acha(arv, "expert", expert)
            o = acha(e["ofertas"], "oferta", oferta) if e else None
            if (not e or not o) and not args.get("criar"):
                return json.dumps({"gravado": False, "motivo": ("o expert não existe no cofre" if not e else "a oferta não existe neste expert"),
                                   "existe_no_cofre": [{"expert": x["expert"], "ofertas": [y["oferta"] for y in x["ofertas"]]} for x in arv],
                                   "o_que_fazer": "Pergunte ao usuário se é uma dessas ou se é para criar. Só chame de novo com criar: true depois do sim."}, ensure_ascii=False)
            destino = {"expert": e["expert"] if e else expert, "oferta": o["oferta"] if o else oferta, "substituir": bool(args.get("substituir")), "aguarda_doc": falta_doc}
            (pasta / "inserir.json").write_text(json.dumps(destino, ensure_ascii=False), encoding="utf-8")
            if falta_doc:
                return (f"Destino registrado: Projetos/{destino['expert']}/{destino['oferta']}/. O Octopus IA grava sozinho assim que o documento chegar. "
                        "Agora termine esta resposta com o documento completo e SÓ ele, começando pela linha --- do frontmatter (sem texto antes nem depois). "
                        "Não chame esta ferramenta de novo.")
            return (f"Pedido de gravação aceito: o Octopus IA grava agora o documento ({doc['tipo']}) em Projetos/{destino['expert']}/{destino['oferta']}/. "
                    "Diga isso ao usuário em uma frase. Não escreva o documento de novo.")
        raise ValueError("ferramenta desconhecida")
    return executar


# ---------------- as pastas do computador (só leitura), para todos os chats ----------------
FERR_COMPUTADOR = [
    _f("listar_pasta", "Lista uma pasta do computador do usuário: subpastas e arquivos (nome, tamanho, se é vídeo/áudio ou texto). Aceita caminho inteiro ou a partir da pasta pessoal, ex.: \"Downloads\", \"Downloads/Anúncios do concorrente\", \"Desktop\", \"Documents/Clientes\". Sem caminho, lista a pasta pessoal.",
       {"caminho": {"type": "string"}}),
    _f("ler_arquivo", "Lê um arquivo de texto do computador do usuário (.txt, .md, .srt, .vtt, .json, .csv, .html, .docx).", {"caminho": {"type": "string"}}, ["caminho"]),
    _f("transcrever_do_computador", "Transcreve com o Whisper, no computador, um vídeo ou áudio, ou todos os de uma pasta. Devolve o texto falado e a duração exata de cada um. Transcreve até 8 arquivos novos por chamada (os já transcritos voltam na hora); se `faltam` vier maior que zero, chame de novo com o mesmo caminho para continuar. Pode levar alguns minutos.",
       {"caminho": {"type": "string", "description": "o arquivo ou a pasta"}, "maximo": {"type": "integer", "description": "quantos arquivos novos nesta chamada (padrão 8)"}}, ["caminho"]),
]
INSTR_COMPUTADOR = """
**As pastas do computador.** Você consegue olhar as pastas e os arquivos do computador do usuário com `listar_pasta`, `ler_arquivo` e `transcrever_do_computador`. Quando ele citar uma pasta ou um arquivo ("na pasta Downloads tem uma pasta X", "pega o vídeo que está no Desktop"), **vá buscar**: liste a pasta para achar o nome exato e leia ou transcreva. Nunca responda que não tem acesso às pastas, nem peça para ele anexar o que já está no computador.
- Vídeo e áudio: `transcrever_do_computador` com o caminho da pasta ou do arquivo. Se voltar `faltam` maior que zero, chame de novo até zerar, e só então trabalhe com tudo. Cada arquivo é um material separado (um anúncio = um vídeo).
- **Você só lê.** Não existe ferramenta para apagar, mover, renomear ou alterar arquivos do computador, e você nunca deve tentar nem sugerir que apagou algo. Se o usuário pedir para apagar ou mover um arquivo, diga que isso você não faz e que ele mesmo precisa fazer.
- **Antes de alterar qualquer coisa** (gravar no Cérebro, substituir um documento, criar expert ou oferta), diga em uma linha o que vai mudar e peça o sim. Só dispense a pergunta quando o próprio pedido já for essa alteração, dita com clareza (ex.: "salva na auditoria da oferta X").
- Pastas do sistema, pastas ocultas e arquivos de senha ou chave não podem ser lidos. Se a ferramenta recusar um caminho, diga isso ao usuário."""


def _executor_computador(pasta=None):
    import computador

    def executar(nome, args):
        try:
            if nome == "listar_pasta":
                return json.dumps(computador.listar(args.get("caminho")), ensure_ascii=False)
            if nome == "ler_arquivo":
                return computador.ler(args.get("caminho"))
            r = computador.transcrever(args.get("caminho"), args.get("maximo") or 8)
            return json.dumps(r, ensure_ascii=False)
        except computador.SemPermissao as e:
            # o macOS bloqueou a pasta: a tela mostra o botão "Permitir acesso" embaixo desta resposta
            nome_pasta = computador._protegida(Path(e.caminho))[0]
            if pasta:
                (pasta / "permissao.json").write_text(json.dumps({"caminho": e.caminho, "nome": nome_pasta}, ensure_ascii=False), encoding="utf-8")
            return (f"O macOS bloqueou o acesso à pasta {nome_pasta} ({e.caminho}). O Octopus IA está mostrando ao usuário, embaixo desta resposta, o botão \"Permitir acesso\". "
                    "Pare aqui: diga em uma frase que é só clicar no botão para liberar e que você continua em seguida. Não mande ele abrir configurações e não tente outros caminhos.")
        except computador.ErroComputador as e:
            raise ValueError(str(e))
        except subprocess.TimeoutExpired:
            raise ValueError("a transcrição passou do tempo; chame de novo com menos arquivos (maximo menor)")
    return executar


# --- Chat do Cérebro: conversa com todas as notas e pode arrumá-las (renomear, reescrever, mudar propriedades)
MODELO_BASE = RAIZ / "cofre-modelo"
FERR_CEREBRO = [
    _f("renomear_nota", "Muda o nome de uma nota do Cérebro (o arquivo continua na mesma pasta). Não vale para as notas de base.",
       {"caminho": {"type": "string", "description": "como veio de listar_notas"}, "novo_nome": {"type": "string", "description": "só o nome, sem pasta e sem .md"}}, ["caminho", "novo_nome"]),
    _f("editar_nota", "Reescreve o texto de uma nota do Cérebro. Mande a nota INTEIRA já corrigida, com o frontmatter (--- ... ---) igual ao original, mudando só o que foi pedido. A versão anterior fica guardada na lixeira. Não vale para as notas de base.",
       {"caminho": {"type": "string"}, "conteudo": {"type": "string", "description": "a nota completa, do --- inicial até o fim"}}, ["caminho", "conteudo"]),
    _f("mudar_propriedades", "Muda propriedades do frontmatter de uma nota (ex.: status, narrativa, formato), sem tocar no texto. Não vale para as notas de base.",
       {"caminho": {"type": "string"}, "propriedades": {"type": "object", "description": "propriedade → novo valor (texto ou número)"}}, ["caminho", "propriedades"]),
]


def _instrucoes_cerebro(cofre):
    return _instrucoes_chat(cofre) + """

## Este chat é o Cérebro
Aqui o usuário conversa com a pasta de arquivos inteira: pergunta o que tem, pede listas e manda arrumar as notas.
- Para responder, olhe antes: `listar_cofre`, `listar_notas`, `consultar_notas` e `ler_nota`. Não responda de memória sobre o que está no Cérebro.
- Para arrumar, use `renomear_nota`, `mudar_propriedades` e `editar_nota`. Leia a nota antes de editar. Em `editar_nota` mande a nota inteira, mexendo só no que foi pedido.
- **O que pode ser alterado:** tudo o que foi criado no uso (o que está em Projetos/ e em Swipe/). **O que não pode:** a raiz do Octopus IA, que é a Biblioteca inteira (modelos, narrativas, formatos, ganchos…), as skills e os agentes (a ferramenta recusa e avisa). Se o usuário pedir para mudar algo da Biblioteca, diga que ela não é alterada por aqui.
- Pedido claro e pequeno (uma a cinco notas): faça e diga o que mudou, nota por nota, em lista curta.
- Pedido que mexe em mais de cinco notas, ou que não está claro: primeiro mostre a lista do que vai mudar (de → para) e espere o usuário confirmar.
- Anúncio continua começando por "AD NN" no nome do arquivo, porque a numeração das remessas depende disso. Pode mudar o que vem depois.
- **Você não exclui nada**, nem nota nem pasta: não existe ferramenta para isso. Se pedirem, diga que excluir é feito pelo próprio usuário, no menu do Cérebro (os três pontinhos ao lado da nota ou da pasta) ou no Ficheiro.
- Você não move nota de pasta e não renomeia pasta de expert ou de oferta.
- Nunca invente o conteúdo de uma nota: se não achou, diga que não achou."""


def _executor_cerebro(pasta, cofre):
    def presa():
        try:
            o = json.loads((pasta / "oferta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return (o["expert"], o["oferta"]) if pasta_oferta(cofre, o.get("expert"), o.get("oferta")) else None

    def alvo(caminho):
        p = _dentro_cofre(cofre, caminho)
        if p and not p.suffix:
            p = p.with_suffix(".md")
        if not p or p.suffix.lower() != ".md" or not p.is_file():
            raise ValueError("nota não encontrada. Use um caminho de listar_notas.")
        rel = p.relative_to(cofre)
        baixo = tuple(x.casefold() for x in rel.parts)      # Mac e Windows não distinguem maiúsculas: "biblioteca/…" é a mesma pasta que "Biblioteca/…"
        if baixo[0] == "biblioteca":                # a raiz do Octopus IA (modelos, narrativas, formatos, ganchos…) não é alterada por agente nenhum
            raise ValueError(f"{rel.as_posix()} faz parte da Biblioteca do Octopus IA, que não é alterada pelo chat.")
        if baixo[:2] == ("swipe", "spy") and len(baixo) == 3 and baixo[2] in ("spy.md", "blacklist.md"):
            raise ValueError(f"{rel.as_posix()} é uma nota do sistema do Spy e não é alterada pelo chat.")
        of = presa()                                # chat com o nó Oferta: só mexe na oferta dele e nas notas do expert dela
        if of and not (baixo[:3] == ("projetos", of[0].casefold(), of[1].casefold()) or (baixo[:2] == ("projetos", of[0].casefold()) and len(baixo) == 3)):
            raise ValueError(f"Este chat está ligado à oferta {of[1]} ({of[0]}) pelo nó Oferta: só altera as notas dela e as do expert (Credenciais e História).")
        if (MODELO_BASE / rel).exists():
            raise ValueError(f"{rel.as_posix()} é uma nota de base do Octopus IA e não é alterada pelo chat.")
        return p, rel

    def carimbar(texto):
        """Nota que tem a propriedade "atualizado" ganha a data de hoje a cada mudança."""
        m = re.match(r"---\n(.*?)\n---", texto, re.S)
        if not m or not re.search(r"^atualizado\s*:", m.group(1), re.M):
            return texto
        return texto[:m.start(1)] + re.sub(r"^atualizado\s*:.*$", f'atualizado: "{time.strftime("%Y-%m-%d")}"', m.group(1), count=1, flags=re.M) + texto[m.end(1):]

    def guardar(p):
        """Antes de mexer, a versão atual vai para a lixeira do Cérebro (dá para recuperar)."""
        lixo = cofre / ".trash"
        lixo.mkdir(exist_ok=True)
        shutil.copy2(p, lixo / f"{p.stem} (antes de editar {time.strftime('%Y-%m-%d %Hh%Mm%S')}){p.suffix}")

    def executar(nome, args):
        if not cofre or not cofre.is_dir():
            return "Nenhuma pasta de arquivos está configurada no Octopus IA."
        p, rel = alvo(args.get("caminho"))
        if nome == "renomear_nota":
            novo = _nome_ok(re.sub(r"\.md$", "", str(args.get("novo_nome") or ""), flags=re.I))
            if not novo:
                raise ValueError('nome inválido (vazio ou com / \\ : * ? " < > |)')
            ad = re.match(r"AD \d+", p.stem) if any(x.casefold() == "anúncios" for x in rel.parts) else None
            if ad and not novo.startswith(ad.group(0)):
                raise ValueError(f"anúncio continua começando por {ad.group(0)}: a numeração das remessas depende disso.")
            destino = p.with_name(novo + ".md")
            if destino.exists():
                raise ValueError("já existe uma nota com esse nome nesta pasta")
            if (MODELO_BASE / destino.relative_to(cofre)).exists():
                raise ValueError("esse nome é de uma nota de base")
            p.rename(destino)
            return f"Renomeada: {rel.as_posix()} → {destino.relative_to(cofre).as_posix()}"
        if nome == "editar_nota":
            texto = str(args.get("conteudo") or "")
            if len(texto.strip()) < 3:
                raise ValueError("conteúdo vazio: mande a nota inteira")
            atual = p.read_text(encoding="utf-8", errors="replace")
            if atual.startswith("---") and not texto.lstrip().startswith("---"):
                raise ValueError("faltou o frontmatter: mande a nota inteira, começando pela linha ---")
            guardar(p)
            p.write_text(carimbar(texto if texto.endswith("\n") else texto + "\n"), encoding="utf-8")
            return f"Nota reescrita: {rel.as_posix()} ({len(atual)} → {len(texto)} caracteres). A versão anterior está na lixeira."
        if nome == "mudar_propriedades":
            props = args.get("propriedades")
            if not isinstance(props, dict) or not props:
                raise ValueError("diga quais propriedades mudar")
            atual = p.read_text(encoding="utf-8", errors="replace")
            m = re.match(r"---\n(.*?)\n---\n?", atual, re.S)
            linhas, resto = (m.group(1).split("\n"), atual[m.end():]) if m else ([], atual)
            for k, v in props.items():
                k = str(k).strip()
                if not re.fullmatch(r"[\w\- ]{1,40}", k):
                    raise ValueError(f"nome de propriedade inválido: {k}")
                val = str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else json.dumps(str(v), ensure_ascii=False)
                i = next((n for n, l in enumerate(linhas) if re.match(rf"{re.escape(k)}\s*:", l)), None)
                if i is None:
                    linhas.append(f"{k}: {val}")
                else:
                    fim = i + 1
                    while fim < len(linhas) and linhas[fim].startswith((" ", "\t", "- ")):      # valor em lista, nas linhas de baixo
                        fim += 1
                    linhas[i:fim] = [f"{k}: {val}"]
            guardar(p)
            p.write_text(carimbar("---\n" + "\n".join(linhas) + "\n---\n" + resto) if "atualizado" not in props else "---\n" + "\n".join(linhas) + "\n---\n" + resto, encoding="utf-8")
            return f"Propriedades mudadas em {rel.as_posix()}: {', '.join(props)}"
        raise ValueError("ferramenta desconhecida")
    return executar


PERMS_PADRAO = {"criar": True, "editar": True}
PRECISA = {"dividir_vsl": "editar", "criar_oferta": "criar", "cadastrar_vsl": "criar", "renomear_nota": "editar", "editar_nota": "editar", "mudar_propriedades": "editar", "baixar_video": "criar",
           "atualizar_anuncio": "editar", "transcrever_youtube": "criar"}
NOME_PERM = {"criar": "Criar notas e pastas", "editar": "Editar notas"}
INSTR_ALTERAR = """
- **Antes de alterar qualquer coisa** (gravar no Cérebro, substituir um documento, criar expert ou oferta), diga em uma linha o que vai mudar e peça o sim. Só dispense a pergunta quando o próprio pedido já for essa alteração, dita com clareza (ex.: "salva no controle de mercado da oferta X").
- **Quando pedir esse sim, termine a mensagem com uma linha `<confirmar>o que vai ser gravado e onde, em poucas palavras</confirmar>`** (ex.: `<confirmar>Salvar Credenciais e História do expert Fulano</confirmar>`). O Octopus IA troca essa linha por um botão **Permitir salvar**: o usuário não precisa digitar nada. Uma linha só, sem mais nada dentro, e só quando estiver de fato esperando o sim para gravar. Quando a resposta vier ("Sim, pode salvar." ou a nota de que o usuário confirmou no botão), grave direto, sem perguntar de novo.
- **Salvar é fazer, não dizer.** Quando o usuário pedir para salvar, guardar, gravar, cadastrar ou subir alguma coisa, ou responder "sim" a um pedido de confirmação seu, a gravação acontece NESTA resposta, pela ferramenta certa (`editar_nota`, `mudar_propriedades`, `cadastrar_vsl`, `criar_oferta`, `salvar_no_cerebro`, `dividir_vsl`, `atualizar_anuncio`). Regras duras:
  - Escrever o conteúdo no chat NÃO é salvar. Nunca responda a um pedido de salvar com o documento na conversa no lugar da gravação.
  - Nunca diga "salvei", "gravado" ou "pronto" se a ferramenta não foi chamada nesta resposta e não respondeu com sucesso. Nunca diga "vou salvar" e termine a resposta: ou grava agora, ou pede o sim com a linha `<confirmar>`.
  - Se já tem tudo (o que gravar e onde), grave direto: não peça confirmação de novo para algo que o usuário acabou de mandar salvar.
  - Se falta alguma coisa (qual expert, qual oferta, o conteúdo), pergunte só isso, em uma linha, e diga claramente: "Ainda não salvei."
  - Depois de gravar, a resposta é curta e conclusiva: "Salvo em <caminho>." mais, no máximo, uma linha do que ficou pendente. Sem repetir o conteúdo.
  - Se a ferramenta recusar (permissão desligada, nota não encontrada, nome inválido), diga exatamente isso e que nada foi salvo."""


INSTR_ARRUMAR = """

**Criar e alterar o que é do usuário.** Todo chat pode criar, pelos modelos, tudo o que o usuário produz (a oferta, a VSL, os anúncios e as remessas, as big ideas, as personas, o dicionário, o controle de mercado, a bíblia, o briefing) e pode alterar depois o que foi criado: essas notas e as do expert (Credenciais e História). Não peça permissão para isso além da confirmação normal de antes de gravar.
**A raiz do Octopus IA não muda:** a Biblioteca inteira (modelos, narrativas, formatos, ângulos, ganchos, estruturas), as skills e os agentes. A ferramenta recusa qualquer alteração nelas.
- `mudar_propriedades`: troca ou preenche propriedades de uma nota sem tocar no texto. É o caminho para pôr as métricas num anúncio ou numa VSL (gasto, faturamento, hook_rate, hold_rate, ic, ctr, cpa, cpm, conversao_checkout, play_rate, retenções, conversão), o link, o status.
- `editar_nota`: muda o texto de uma nota. Leia antes (`ler_nota`) e mande a nota inteira, com o cabeçalho, mexendo só no que foi pedido. A versão anterior vai para a lixeira.
- `renomear_nota`: muda o nome da nota. Anúncio continua começando por "AD NN".
- **Você não exclui nada.** Não existe ferramenta para excluir nota nem pasta: se pedirem, diga que excluir é feito pelo próprio usuário, no menu do Cérebro (os três pontinhos) ou no Ficheiro.
- **Credenciais e História do expert** ficam em `Projetos/{Expert}/Credenciais.md` e `Projetos/{Expert}/História.md` e já existem, a partir do modelo. Para guardar o que o usuário contar, escreva DENTRO delas com `editar_nota`, embaixo do título da seção certa, mantendo o cabeçalho e os títulos (a função `#salvar-expert` traz o passo a passo). Não crie outra nota para isso.
- Se o expert ou a oferta ainda não existem, crie com `criar_oferta`, depois do sim do usuário.
- Pedido claro e pequeno (até cinco notas): faça e diga o que mudou. Acima disso, ou sem estar claro, mostre a lista do que vai mudar (de → para) e espere o sim.
- **Controle de mercado:** qualquer chat pode alimentar o controle de mercado de uma oferta com anúncios do usuário ou de concorrentes. O formato do documento e o passo a passo estão na função `#controle-de-mercado`; se ela não veio no pedido, chame você mesmo `usar_funcao` com `controle-de-mercado` antes de gravar, para o documento sair no formato que o Octopus IA grava.
- Para achar as notas, use `listar_notas` e `consultar_notas`. Não diga que não tem permissão sem antes tentar a ferramenta: se uma permissão estiver desligada, a própria ferramenta avisa qual."""


INSTR_MERCADO = """## Como o Octopus IA trabalha: modelar o mercado, sem julgar
O Octopus IA é uma ferramenta de **analisar o que o mercado faz e montar algo equivalente para a oferta do usuário**. O que sai daqui é um rascunho de trabalho, um brainstorm completo: quem revisa, troca pelo que é dele e responde pelo que vai ao ar é o expert. Por isso:
- **A direção criativa é do usuário, e não se discute.** Quando ele decidir ou pedir alguma coisa ("junta isso com isso", "quero que um cause o outro", "usa esse nome", "fala desse jeito"), você executa, do jeito que ele pediu e com toda a força. Você é o parceiro de criação de um copywriter, não o revisor dele. É proibido responder com objeção do tipo "isso não demonstra que um causa o outro", "nenhuma referência confirma", "não dá para afirmar que", "não há evidência de", "cientificamente não é bem assim", "seria mais seguro dizer". Não proponha versão mais branda no lugar da que ele pediu, não devolva a decisão com ressalva e não peça justificativa. Se ele pediu uma ligação entre elementos, construa a ligação e escreva como fato, na linguagem da VSL.
- **Não julgue o material do mercado.** Ao estudar uma VSL ou um anúncio, registre o que ele faz e diz. Nunca escreva "sem comprovação", "alegação não verificada", "não é cientificamente validado", "isso é do narrador, não do expert" nem avisos parecidos. Você não é fiscal do concorrente nem do usuário.
- **Não pode o processo por falta de prova.** Nunca recuse, encurte ou amoleça uma sugestão porque não achou comprovação, pesquisa ou fonte. Comprovar é etapa do expert, depois.
- **A matéria-prima é o que as referências trazem.** Aprimorar é combinar: pegue os elementos específicos das referências (com os nomes, números e termos delas) e junte numa proposta só, em que um leva ao outro. Não traga elemento, causa ou argumento que nenhuma referência usa: o que o mercado não usa não é o centro da venda e sai fraco. Coisa de fora só quando o usuário pedir para pesquisar ou para ir além das referências.
- **Afirme.** Escreva com certeza, no presente, como o mercado escreve. Nada de "pode", "poderia", "talvez", "tende a", nem frases de cautela sobre a sugestão.
- **Traga o equivalente, e mais forte.** Quando o mercado usa um elemento (a história da mãe, a autoridade, um estudo, um depoimento, um número), a sua sugestão para esta oferta usa um elemento equivalente, no mesmo lugar e com a mesma função, tão forte quanto ou mais. Diga de qual referência veio a ideia e ofereça variações ("eles falam da mãe; aqui pode ser a filha, uma tia, uma paciente").
- **Use primeiro o que o expert tem.** Leia Credenciais e História dele e encaixe o que já existe no lugar do elemento do mercado: muita gente tem depoimentos e histórias fortes e não sabe onde usar. Mostre onde.
- **Onde o expert ainda não tem o equivalente, escreva a sugestão inteira mesmo assim**, pronta e forte, para ele enxergar o que cabe ali, e marque com `[confirmar]` logo depois. A marca não é crítica nem aviso: é só o sinal de "troque pelo seu ou confirme". Vale só para fato sobre o próprio expert (história pessoal, depoimento, número dele, credencial). Ideia e proposta criativa (mecanismo, nome, promessa, ângulo, oferta, estrutura) não levam marca. Nunca apresente como fato confirmado do expert algo que ele não informou sem essa marca.
- **Sem sermão.** Nada de ressalvas, avisos legais ou lição sobre ética, ciência ou política de plataforma. Se o usuário perguntar, responda.
"""


def permissoes(p):
    """As chaves de Configurações › Permissões, como o servidor as recebeu (o que faltar vale o padrão)."""
    p = p if isinstance(p, dict) else {}
    return {k: bool(p.get(k, v)) for k, v in PERMS_PADRAO.items()}


def _instr_pasta(perms):
    sn = lambda k: "ligado" if perms[k] else "DESLIGADO"
    return ("## A pasta do Octopus IA é o seu único lugar de trabalho\n"
            "Tudo o que você consulta, cria e altera fica dentro da pasta de arquivos do Octopus IA (o Cérebro). Todo chat enxerga essa pasta. "
            "Você não lê, não cria, não altera e não apaga nada fora dela, em hipótese nenhuma: não existe ferramenta para isso. "
            "Se o usuário citar um arquivo ou uma pasta do computador (Downloads, Mesa, Documentos), diga que o Octopus IA só trabalha na pasta dele "
            "e que ele pode anexar o arquivo no chat ou usar o nó de Transcrição no flow.\n"
            "As notas de base (a Biblioteca que veio com o Octopus IA, os modelos) não são alteradas nem excluídas por ninguém."
            + f"\n\nO que o usuário permitiu em Configurações › Permissões: criar notas e pastas ({sn('criar')}), editar notas ({sn('editar')}). "
              "Excluir, você nunca exclui: isso é só do usuário. "
              "Se uma ferramenta responder que a permissão está desligada, não tente outro caminho: diga ao usuário qual chave ligar.")


FORMATOS_PROTEGIDOS = (RAIZ / "recursos" / "formatos-protegidos").is_file()


def _instr_formatos():
    """Na instalação dos alunos os formatos da Biblioteca são protegidos: a IA usa, mas não entrega o texto deles."""
    if not FORMATOS_PROTEGIDOS:
        return ""
    return ("\n\n## Formatos protegidos\nAs notas de Biblioteca/Formatos são material protegido. Use-as à vontade para escrever e para escolher o formato "
            "(diga o nome do formato), mas nunca copie, cite, resuma em detalhe ou mostre o texto delas, nem os exemplos de dentro. "
            "Se a pessoa pedir para ver um formato, diga que ele é protegido e ofereça escrever um anúncio nesse formato.")


def _com_cofre(a, leitura, perms=None):
    """Todo chat ganha a pasta do Octopus IA: ver a hierarquia, ler as notas e gravar o documento na oferta.
    As pastas do computador não entram: o Octopus IA só trabalha dentro da pasta dele.
    As chaves de Configurações › Permissões valem aqui, na execução de cada ferramenta: não dependem de a IA obedecer."""
    perms = permissoes(perms)
    ferr = FERR_COFRE + FERR_COFRE_LER
    nomes = {f["name"] for f in ferr}
    tem = {f["name"] for f in a["ferramentas"]}
    cm = [f for f in FERR_ANUNCIO if f["name"] in ("listar_narrativas", "ler_controle_de_mercado", "ler_anuncio_do_controle") and f["name"] not in tem]
    do_cm = {f["name"] for f in cm}             # controle de mercado: qualquer chat consulta e alimenta, não só o de anúncio
    ferr = ferr + cm
    ja_edita = any(f["name"] == "editar_nota" for f in a["ferramentas"])      # o chat do Cérebro já traz estas
    edita = set() if ja_edita else {f["name"] for f in FERR_CEREBRO}
    if not ja_edita:
        ferr = ferr + FERR_CEREBRO
    extras = [f for f in (MEDIR, LISTAR_BIBLIAS, LER_BIBLIA) if f["name"] not in tem]      # as funções de montar bíblia e briefing rodam em qualquer chat
    da_biblia, do_briefing = {f["name"] for f in extras if f is MEDIR}, {f["name"] for f in extras if f is not MEDIR}
    ferr = ferr + extras
    if funcoes_livres():
        ferr = ferr + [_f("usar_funcao", "Carrega o passo a passo e o formato de uma função do Octopus IA, para você seguir neste pedido. Chame antes de fazer o trabalho da função.",
                          {"id": {"type": "string", "description": " | ".join(f["id"] for f in funcoes_livres())}}, ["id"])]

    def _exec(pasta, cofre):
        ex, meu, arruma = a["executor"](pasta, cofre), _executor_cofre(pasta, cofre), _executor_cerebro(pasta, cofre)
        mercado = _executor_anuncio(pasta, cofre) if do_cm else None

        def executar(nome, args):
            if nome == "usar_funcao":
                fid = str(args.get("id") or "").strip().lstrip("#").lower()
                f = next((x for x in funcoes_livres() if x["id"] == fid), None)
                return _bloco_skill(f, cofre, "chamada por você para este pedido") if f else "Função não encontrada. As que existem: " + ", ".join(x["id"] for x in funcoes_livres())
            if nome in da_biblia:
                return _executor_biblia(pasta, cofre)(nome, args)
            if nome in do_briefing:
                return _executor_briefing(pasta, cofre)(nome, args)
            falta = PRECISA.get(nome)
            if nome == "salvar_no_cerebro":
                falta = "editar" if args.get("substituir") and not perms["editar"] else "criar"
            elif nome == "cadastrar_vsl" and args.get("substituir"):      # trocar uma VSL que já existe é edição, não criação
                falta = "editar"
            elif nome == "dividir_vsl":                                     # na nota do Cérebro é edição; a cópia na oferta (pelo anexo) é criação
                falta = "editar" if args.get("caminho") else ("criar" if (args.get("expert") or args.get("oferta")) else None)
            if falta and not perms[falta]:
                return (f"Não foi feito: a permissão \"{NOME_PERM[falta]}\" está desligada em Configurações › Permissões. "
                        "Diga isso ao usuário em uma frase e que ele pode ligar lá. Não tente de outro jeito.")
            return mercado(nome, args) if nome in do_cm else arruma(nome, args) if nome in edita else meu(nome, args) if nome in nomes else ex(nome, args)
        return executar
    return {"instrucoes": lambda cofre: a["instrucoes"](cofre) + "\n\n" + _instr_pasta(perms) + "\n\n"
            + INSTR_COFRE.replace("{leitura}", INSTR_COFRE_LER + ("" if leitura else INSTR_COFRE_SEM_LER))
            + "\n" + INSTR_ALTERAR + ("" if ja_edita else INSTR_ARRUMAR) + _instr_funcoes() + "\n\n" + INSTR_MERCADO + _instr_formatos(),
            "ferramentas": list(a["ferramentas"]) + ferr, "executor": _exec}


def _instrucoes_chat(cofre):
    return """Você é o assistente do Octopus IA, um sistema de agentes para marketing de resposta direta (VSL, anúncios, funil).
Responda sempre em português do Brasil, de forma direta e prática.
- Você não tem terminal nem internet. Os arquivos que você alcança são os da pasta do Octopus IA (regras mais abaixo). O que o usuário conectou no flow (inteligência, bíblia do nicho, briefing de tese) chega no texto da mensagem, marcado como contexto. O Cérebro (a pasta de arquivos do Octopus IA) você consulta pelas ferramentas.
- Use o contexto conectado para responder. Quando citar algo dele, diga de onde veio.
- O que é do mercado (o que uma VSL ou um anúncio de referência diz) vem do material ligado: não atribua a um concorrente algo que o material não mostra."""


def _executor_nenhum(pasta, cofre):
    def executar(nome, args):
        raise ValueError("este agente não tem ferramentas")
    return executar


AGENTES = {
    "biblia": {"instrucoes": _instrucoes_biblia, "ferramentas": [MEDIR], "executor": _executor_biblia},
    "briefing": {"instrucoes": _instrucoes_briefing, "ferramentas": [LISTAR_BIBLIAS, LER_BIBLIA], "executor": _executor_briefing},
    "chat": {"instrucoes": _instrucoes_chat, "ferramentas": [], "executor": _executor_nenhum},
    "blocos": {"instrucoes": _instrucoes_blocos, "ferramentas": [MEDIR, CONTAR], "executor": _executor_blocos},
    "persona": {"instrucoes": _instrucoes_persona, "ferramentas": [f for f in FERR_ANUNCIO if f["name"] in ("listar_angulos", "listar_oferta", "ler_nota_oferta", "ler_controle_de_mercado", "ler_anuncio_do_controle", "listar_personas")], "executor": _executor_anuncio},
    "anuncio": {"instrucoes": _instrucoes_anuncio, "ferramentas": FERR_ANUNCIO, "executor": _executor_anuncio},
    "cerebro": {"instrucoes": _instrucoes_cerebro, "ferramentas": FERR_CEREBRO, "executor": _executor_cerebro},
}


def contexto(itens, pasta, cofre=None, estado=None):
    """Monta o texto e as imagens do que está conectado ao nó no flow.
    itens: [{"tipo": "texto"|"doc", "titulo", "texto"} | {"tipo": "arquivo", "flow", "no", "nome"}]"""
    partes, imagens = [], []
    of = next((it for it in itens or [] if it.get("tipo") == "oferta"), None)
    arq_of = pasta / "oferta.json"
    if of and pasta_oferta(cofre, of.get("expert"), of.get("oferta")):
        pasta.mkdir(parents=True, exist_ok=True)
        arq_of.write_text(json.dumps({"expert": of.get("expert"), "oferta": of.get("oferta")}, ensure_ascii=False), encoding="utf-8")
        partes.append(f"### Oferta deste flow\nExpert: {of.get('expert')} · Oferta: {of.get('oferta')} (Projetos/{of.get('expert')}/{of.get('oferta')} no cofre). "
                      "É nesta oferta que este chat trabalha: é nela que você grava e altera. Para consultar, você enxerga o Cérebro inteiro (os outros experts e ofertas, as VSLs, a Biblioteca). "
                      "Preencha expert e oferta no documento com esses nomes e, se o usuário pedir para salvar no Cérebro, grave nela sem perguntar. "
                      "Para consultar o que ela já tem (bíblia, tese, big ideas, anúncios), use as ferramentas de leitura que você tiver.")
        vsl = re.sub(r"[^A-Za-z0-9 ]", "", str(of.get("vsl") or ""))[:8].upper()
        if vsl:
            partes.append(f"### Versão da VSL deste flow\n{vsl}. Os anúncios deste flow mandam para a VSL {vsl}: preencha o campo VSL com {vsl} e não pergunte a versão.")
        try:
            import criativos
            st = criativos.situacao_anuncios(cofre, of.get("expert"), of.get("oferta"))
            rem = ", ".join(f"Remessa {r['remessa']:02d} ({r['anuncios']} anúncios)" for r in st["remessas"]) or "nenhuma ainda"
            try:
                no_chat = max(0, min(9999, int(of.get("ultimoNoChat") or 0)))      # anúncios já escritos neste chat e ainda não salvos: a contagem segue deles
            except (TypeError, ValueError):
                no_chat = 0
            prox = max(st["proximo"], no_chat + 1)
            try:
                rem_chat = int(of.get("remessa") or 0)
            except (TypeError, ValueError):
                rem_chat = 0
            escolhida = bool(rem_chat)
            if not rem_chat:
                rem_chat = (st["remessas"][-1]["remessa"] if st["remessas"] else 0) + 1
            partes.append(f"### Anúncios já salvos nesta oferta\n{st['total']} anúncio(s); o último salvo é o AD {st['ultimo']:02d}. Remessas: {rem}."
                          + (f" Neste chat já foram escritos anúncios até o número {no_chat}, ainda não salvos." if no_chat >= st["proximo"] else ""))
            partes.append(f"### Remessa e numeração deste chat (regra fixa)\n"
                          + (f"O usuário escolheu trabalhar na **Remessa {rem_chat:02d}**. Não pergunte a remessa de novo e não use outra.\n" if escolhida or not st["remessas"]
                             else f"A remessa ainda não foi escolhida. Antes de escrever qualquer anúncio, pergunte: \"Estamos na Remessa {st['remessas'][-1]['remessa']:02d} ({st['remessas'][-1]['anuncios']} anúncios). Quer criar mais anúncios dentro dela ou abrir a Remessa {rem_chat:02d}?\" e espere a resposta. Se ele não disser, é a Remessa {rem_chat:02d}.\n") +
                          f"O próximo anúncio é o **{prox}**: numere a partir dele, em sequência, sem repetir e sem recomeçar (`## Anúncio {prox}: …`, `## Anúncio {prox + 1}: …`). "
                          f"Nunca use o número 1 se o próximo não for 1. No documento: título `# Anúncios: Remessa {rem_chat:02d}, <tema>` e cabeçalho `remessa: {rem_chat}`.\n"
                          "Escrever não é salvar: entregue os anúncios e só grave quando o usuário pedir. Ao gravar, eles entram nessa remessa, com esses números.")
        except Exception:
            pass
    elif arq_of.exists():
        arq_of.unlink()
    for it in itens or []:
        titulo = str(it.get("titulo") or "").strip()[:120]
        if it.get("tipo") in ("texto", "doc"):
            t = str(it.get("texto") or "").strip()
            if t:
                # texto longo (uma VSL colada, um documento) também vira arquivo da conversa, para a ferramenta medir_blocos achar pelo nome
                ref = ""
                if len(t) > 1500:
                    try:
                        arq = nome_anexo(re.sub(r"\s+", " ", re.sub(r"[^\w \-()]", " ", (titulo or "texto").replace("—", "-"))).strip()[:80] or "texto")
                        (pasta / "anexos").mkdir(parents=True, exist_ok=True)
                        (pasta / "anexos" / arq).write_text(t, encoding="utf-8")
                        ref = f" (em medir_blocos, use anexo: \"{arq}\")"
                    except (ValueError, OSError):
                        pass
                partes.append(f"### Contexto conectado: {titulo or 'texto'}{ref}\n{t}")
        elif it.get("tipo") == "biblia_cofre":
            permitidas = {p.relative_to(cofre).as_posix(): p for p in _biblias(cofre)} if cofre else {}
            arq = permitidas.get(str(it.get("caminho") or ""))
            if arq:
                partes.append(f"### Contexto conectado: {titulo or 'bíblia do nicho'} — {arq.relative_to(cofre).as_posix()}\n{arq.read_text(encoding='utf-8')}")
        elif it.get("tipo") == "briefing_cofre":
            permitidas = {p.relative_to(cofre).as_posix(): p for p in _briefings(cofre)} if cofre else {}
            arq = permitidas.get(str(it.get("caminho") or ""))
            if arq:
                partes.append(f"### Contexto conectado: {titulo or 'Briefing de tese'} — {arq.relative_to(cofre).as_posix()}\n{arq.read_text(encoding='utf-8')}")
        elif it.get("tipo") == "blocos_no":
            import armazem
            pasta_inteligencia(it.get("flow"), it.get("no"))            # valida os ids
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / "blocos.json").write_text(json.dumps({"no": it.get("no"), "pasta": str(armazem.pasta_arquivos(cofre, estado, it.get("flow")))}, ensure_ascii=False), encoding="utf-8")
        elif it.get("tipo") == "arquivo":
            import armazem
            pasta_inteligencia(it.get("flow"), it.get("no"))            # valida os ids
            nome = nome_arquivo(it.get("nome"))
            arq = armazem.pasta_arquivos(cofre, estado, it.get("flow")) / nome
            if not arq.is_file():                                       # arquivos antigos, de antes do cofre
                arq = FLOWS / it.get("flow") / it.get("no") / nome
            if not arq.is_file():
                continue
            if arq.suffix.lower() in IMAGEM_EXT:
                imagens.append(str(arq))
                partes.append(f"### Contexto conectado: imagem {arq.name} ({titulo or 'inteligência'}) — segue anexada.")
            else:
                t = arq.read_text(encoding="utf-8", errors="replace")
                # transcrição conectada também vale para a ferramenta medir_blocos
                (pasta / "anexos").mkdir(parents=True, exist_ok=True)
                if arq.suffix.lower() in {".txt", ".md", ".srt", ".vtt", ".json"}:
                    (pasta / "anexos" / arq.name).write_text(t, encoding="utf-8")
                partes.append(f"### Contexto conectado: arquivo {arq.name} ({titulo or 'inteligência'}, {len(t):,} caracteres)\n```\n{t}\n```".replace(",", "."))
    return "\n\n".join(partes), imagens[:8]


NOMES = {"biblia": "Bíblia do nicho", "briefing": "Briefing de tese", "anuncio": "Copy de anúncio", "blocos": "Blocos de VSL"}


def _chat_com_agentes(habilidades):
    """Chat do flow com agentes ligados antes dele: junta as instruções e as ferramentas de cada um."""
    habs = [h for h in dict.fromkeys(habilidades) if h in NOMES][:1]     # um agente por chat

    PEDE = {"biblia": "as VSLs dos concorrentes (transcrição, arquivo ou texto colado)",
            "briefing": "a bíblia do nicho (até três)", "blocos": "o Briefing de tese (no nó Blocos de VSL)"}
    if habs and habs[0] == "anuncio":          # nos flows de Criativos o chat JÁ É o agente de anúncio
        return AGENTES["anuncio"]

    def instrucoes(cofre):
        h = habs[0]
        partes = [_instrucoes_chat(cofre),
                  f"## Este chat é o agente {NOMES[h]}\nNeste flow, o agente {NOMES[h]} está ligado a este chat. Este chat faz "
                  + ("SÓ essa tarefa: escrever a VSL um bloco por vez, cada bloco no formato da skill. " if h == "blocos" else
                     f"SÓ essa tarefa, sempre com o mesmo resultado: o documento final de {NOMES[h]}, completo, no formato do modelo. ") +
                  f"Siga o processo e as regras do agente à risca. Se ainda não chegou {PEDE[h]} (no contexto ou na mensagem), "
                  f"peça isso antes de qualquer coisa. Se pedirem outra coisa, diga em uma frase que este chat só faz {NOMES[h]} "
                  "e que, para outra tarefa, é só usar outro chat no flow. A entrega final começa pela linha --- do frontmatter "
                  "do modelo (é o que faz o botão Salvar no Cérebro aparecer)."]
        for h in habs:
            partes.append(f"=== Agente: {NOMES[h]} ===\n" + AGENTES[h]["instrucoes"](cofre))
        return "\n\n".join(partes)

    def executor(pasta, cofre):
        por_nome = {}
        for h in habs:
            ex = AGENTES[h]["executor"](pasta, cofre)
            for f in AGENTES[h]["ferramentas"]:
                por_nome[f["name"]] = ex
        def executar(nome, args):
            if nome not in por_nome:
                raise ValueError("ferramenta desconhecida")
            return por_nome[nome](nome, args)
        return executar

    ferramentas = [f for h in habs for f in AGENTES[h]["ferramentas"]]
    return {"instrucoes": instrucoes, "ferramentas": ferramentas, "executor": executor}


def preparar(agente, conversa, cofre, anexos, habilidades=None, perms=None):
    """Guarda os anexos e devolve (pasta, instruções, ferramentas, executor, texto dos anexos)."""
    if agente not in AGENTES:
        raise ValueError("este agente ainda não está ligado ao Codex")
    habilidades = [h for h in (habilidades or []) if isinstance(h, str)]
    com_youtube = "youtube" in habilidades or "tiktok" in habilidades      # "tiktok": flows antigos, de quando o nó era de TikTok
    habilidades = [h for h in habilidades if h not in ("youtube", "tiktok")]
    a = _chat_com_agentes(habilidades) if agente == "chat" and habilidades else AGENTES[agente]
    if com_youtube:                             # nó YouTube ligado: o agente do chat ganha a busca
        base = a
        def _exec(pasta, cofre, base=base):
            ex = base["executor"](pasta, cofre)
            return lambda nome, args: (_executor_youtube(nome, args, cofre) if nome in ("buscar_youtube", "baixar_video")
                                       else _executor_blocos(pasta, cofre)(nome, args) if nome == "transcrever_youtube" else ex(nome, args))
        blocos = agente == "blocos" or "blocos" in habilidades
        a = {"instrucoes": lambda cofre, base=base: base["instrucoes"](cofre) + "\n\n" + INSTR_YOUTUBE + (INSTR_YT_BLOCOS if blocos else ""),
             "ferramentas": list(base["ferramentas"]) + FERR_YOUTUBE + ([TRANSCREVER_YT] if blocos else []), "executor": _exec}
    a = _com_cofre(a, leitura=not (agente == "biblia" or "biblia" in habilidades), perms=perms)
    pasta = pasta_conversa(conversa)
    (pasta / "anexos").mkdir(parents=True, exist_ok=True)
    blocos = []
    for an in anexos or []:
        nome = nome_anexo(an.get("nome"))
        texto = str(an.get("texto") or "")
        (pasta / "anexos" / nome).write_text(texto, encoding="utf-8")
        blocos.append(f"### Anexo: {nome} ({len(texto):,} caracteres)\n```\n{texto}\n```".replace(",", "."))
    instr = a["instrucoes"](cofre)
    vic = cofre / "Biblioteca" / "Vícios de IA.md" if cofre else None
    if vic and vic.is_file() and "# Vícios de IA" not in instr:      # os vícios valem em todos os processos, não só nos de anúncio e VSL
        instr += ("\n\n## Biblioteca/Vícios de IA (nota do cofre)\nVale para todo texto que você escrever para ser lido ou falado pelo público (copy, roteiro, exemplo de fala). "
                  "Não se aplica ao que você transcreve ou cita de material dos outros.\n\n" + _sem_frontmatter(vic.read_text(encoding="utf-8")))
    return pasta, instr, a["ferramentas"], a["executor"](pasta, cofre), "\n\n".join(blocos)
