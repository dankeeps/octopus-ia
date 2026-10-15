"""Automações do Octopus IA: tarefas que rodam sozinhas no horário marcado.

Ficam em dados/automacoes.json, na pasta de dados do aplicativo (do computador, não do cofre). Um vigia roda junto com o
servidor e, a cada meio minuto, dispara as que estão na hora. Se o Octopus estava fechado no
horário, a automação roda quando ele abrir, desde que ainda seja o mesmo dia.

Tipos: "spy" (busca na Biblioteca de Anúncios) e "tiktok" (busca no TikTok pelo Apify, que cobra por vídeo
na conta de quem é dono do token), com as palavras e os filtros guardados. Não gastam IA.
"""
import json
import re
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path

import tiktok

RAIZ = Path(__file__).resolve().parent
from locais import LOCAL
ARQ = LOCAL / "dados" / "automacoes.json"
ARQ_WORK = LOCAL / "dados" / "trabalhos.json"      # cada vez que uma automação rodou (a sub-aba Work)
TIPOS = ("spy", "tiktok", "youtube")
ATIVOS = ("spy",)          # por enquanto só o Spy no Facebook roda; TikTok e YouTube aparecem como "em breve"
codex = None            # o servidor põe aqui a ponte com o Codex (só o resumo do YouTube usa IA)
yt_rodando = set()      # automações de YouTube em andamento
PAISES = ("BR", "US", "PT", "ES", "MX", "AR", "CO", "CL", "PE", "ALL")
trava = threading.RLock()


class ErroAuto(Exception):
    pass


def _ler():
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def _gravar(lista):
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARQ.with_suffix(".tmp")
    tmp.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARQ)


def _ler_work():
    try:
        d = json.loads(ARQ_WORK.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def _gravar_work(lista):
    ARQ_WORK.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARQ_WORK.with_suffix(".tmp")
    tmp.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARQ_WORK)


def _registrar(a, ultima):
    """Uma linha no Work para cada rodada. Os favoritos nunca saem; do resto ficam as 300 mais recentes."""
    with trava:
        lista = _ler_work()
        t = {"id": secrets.token_hex(4), "auto": a["id"], "nome": a["nome"], "tipo": a["tipo"], "palavras": a["consulta"]["palavras"],
             "quando": ultima["quando"], "status": ultima["status"], "mensagem": ultima.get("mensagem") or "",
             "busca": ultima.get("busca"), "nota": ultima.get("nota"), "favorito": False}
        lista.insert(0, t)
        soltos = [x for x in lista if not x.get("favorito")][300:]
        _gravar_work([x for x in lista if x not in soltos])
    return t["id"]


def _atualizar_work(tid, **campos):
    with trava:
        lista = _ler_work()
        for t in lista:
            if t["id"] == tid:
                t.update(campos)
        _gravar_work(lista)


def trabalhos(spy=None):
    """O Work, do mais novo para o mais antigo, com a situação de cada busca (quantas bibliotecas ou vídeos vieram)."""
    with trava:
        lista = _ler_work()
    for t in lista:
        try:
            if t["tipo"] == "spy" and spy is not None and t.get("busca"):
                b = spy.buscas.get(t["busca"])
                if b:
                    t["estado"] = b.get("status")
                    t["qtd"] = len([r for r in b.get("resultados") or [] if r.get("confere") is True and not r.get("ja_monitorada")])
                else:
                    t["estado"] = "apagada"
            elif t["tipo"] == "tiktok" and t.get("busca"):
                b = tiktok.busca(t["busca"])
                t["estado"], t["qtd"] = b.get("status"), len(b.get("videos") or [])
            elif t["tipo"] == "youtube":
                if t.get("status") == "rodando" and t.get("auto") not in yt_rodando:
                    t["status"], t["mensagem"] = "erro", "O Octopus IA foi fechado durante a automação."
                t["estado"] = t.get("status")
        except Exception:
            t["estado"] = "apagada"
    return lista


def favoritar(tid, valor):
    _atualizar_work(tid, favorito=bool(valor))


def tirar_trabalho(tid):
    """Tira a linha do Work. A busca e o relatório continuam onde estão."""
    with trava:
        _gravar_work([t for t in _ler_work() if t["id"] != tid])


def _agora():
    return int(time.time() * 1000)


def _vencimento(a, quando=None):
    """O horário marcado de hoje (em ms), se hoje é um dos dias e a hora já chegou; senão None."""
    d = quando or datetime.now()
    if d.weekday() not in (a.get("dias") or []):
        return None
    h, m = (int(x) for x in a["hora"].split(":"))
    alvo = d.replace(hour=h, minute=m, second=0, microsecond=0)
    return int(alvo.timestamp() * 1000) if d >= alvo else None


def _proxima(a):
    """Próxima vez que vai rodar (ms), para mostrar no cartão."""
    if not a.get("ativa") or not a.get("dias"):
        return None
    h, m = (int(x) for x in a["hora"].split(":"))
    agora = datetime.now()
    for i in range(8):
        d = datetime.fromtimestamp(agora.timestamp() + i * 86400).replace(hour=h, minute=m, second=0, microsecond=0)
        if d.weekday() in a["dias"] and d > agora:
            return int(d.timestamp() * 1000)
    return None


def listar():
    with trava:
        lista = _ler()
    for a in lista:
        if (a.get("ultima") or {}).get("status") == "rodando" and a["id"] not in yt_rodando:      # o Octopus fechou no meio
            a["ultima"] = {**a["ultima"], "status": "erro", "mensagem": "O Octopus IA foi fechado durante a automação."}
        a["proxima"] = _proxima(a)
    return lista


def _num(v, pad, lo, hi):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return pad


def salvar(dados):
    """Cria (sem id) ou altera (com id) uma automação. Devolve a lista."""
    tipo = str(dados.get("tipo") or "spy")
    if tipo not in TIPOS:
        raise ErroAuto("tipo de automação desconhecido")
    if tipo not in ATIVOS:
        raise ErroAuto("Essa automação chega em breve. Por enquanto, só o Spy no Facebook.")
    nome = re.sub(r"\s+", " ", str(dados.get("nome") or "")).strip()[:60]
    hora = str(dados.get("hora") or "")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hora):
        raise ErroAuto("Escolha o horário.")
    dias = sorted({int(x) for x in (dados.get("dias") or []) if str(x).isdigit() and 0 <= int(x) <= 6})
    if not dias:
        raise ErroAuto("Escolha pelo menos um dia da semana.")
    c = dados.get("consulta") or {}
    palavras = []
    for x in c.get("palavras") or []:
        x = re.sub(r"\s+", " ", str(x)).strip()[:80]
        if x and x.lower() not in [p.lower() for p in palavras]:
            palavras.append(x)
    if not palavras or len(palavras) > 10:
        raise ErroAuto("Escolha de uma a dez palavras-chave.")
    pais = str(c.get("pais") or "BR").upper()
    if pais not in PAISES:
        raise ErroAuto("país inválido")
    if tipo == "youtube":
        consulta = {"palavras": palavras, "por_termo": _num(c.get("por_termo"), 5, 1, 20),
                    "formato": c.get("formato") if c.get("formato") in ("todos", "shorts", "longos") else "todos",
                    "min_views": _num(c.get("min_views"), 0, 0, 10 ** 9), "baixar": bool(c.get("baixar")),
                    "transcrever": bool(c.get("transcrever")), "resumir": bool(c.get("resumir"))}
    elif tipo == "tiktok":
        consulta = {"palavras": palavras, "pais": pais if pais in tiktok.PAISES else "BR", "por_palavra": _num(c.get("por_palavra"), 30, 1, 200),
                    "min_views": _num(c.get("min_views"), 0, 0, 10 ** 9),
                    "ordem": c.get("ordem") if c.get("ordem") in tiktok.ORDENS else tiktok.ORDENS[0],
                    "periodo": c.get("periodo") if c.get("periodo") in tiktok.PERIODOS else tiktok.PERIODOS[0]}
    else:
        consulta = {"palavras": palavras, "pais": pais, "min_anuncios": _num(c.get("min_anuncios"), 5, 1, 10000),
                    "min_dias": _num(c.get("min_dias"), 7, 0, 3650), "max_bibliotecas": _num(c.get("max_bibliotecas"), 20, 1, 100),
                    "ver_monitoradas": bool(c.get("ver_monitoradas"))}
    campos = {"tipo": tipo, "nome": nome or {"tiktok": "TikTok · ", "youtube": "YouTube · "}.get(tipo, "Facebook · ") + ", ".join(palavras[:2]), "hora": hora, "dias": dias, "consulta": consulta,
              "nicho": re.sub(r"\s+", " ", str(dados.get("nicho") or "")).strip()[:60],
              "secao": str(dados.get("secao") or "")[:60], "lingua": _num(dados.get("lingua"), 0, 0, 2)}
    with trava:
        lista = _ler()
        aid = str(dados.get("id") or "")
        a = next((x for x in lista if x["id"] == aid), None)
        if aid and not a:
            raise ErroAuto("automação não encontrada")
        if not a:
            a = {"id": secrets.token_hex(4), "ativa": True, "criada": _agora(), "ultima": None}
            lista.append(a)
        a.update(campos)
        a["marco"] = _agora()      # mudou agora: o horário de hoje que já passou não dispara
        _gravar(lista)
    return listar()


def apagar(aid):
    with trava:
        _gravar([a for a in _ler() if a["id"] != aid])
    return listar()


def ligar(aid, valor):
    with trava:
        lista = _ler()
        for a in lista:
            if a["id"] == aid:
                a["ativa"] = bool(valor)
                if valor:
                    a["marco"] = _agora()
        _gravar(lista)
    return listar()


def _anotar(aid, **campos):
    with trava:
        lista = _ler()
        for a in lista:
            if a["id"] == aid:
                a.update(campos)
        _gravar(lista)


def rodar(aid, spy, cofre):
    """Dispara uma automação agora. Devolve o que anotou em 'ultima'."""
    with trava:
        a = next((x for x in _ler() if x["id"] == aid), None)
    if not a:
        raise ErroAuto("automação não encontrada")
    if a["tipo"] not in ATIVOS:
        raise ErroAuto("Essa automação chega em breve. Por enquanto, só o Spy no Facebook.")
    ultima = {"quando": _agora(), "status": "ok", "mensagem": "", "busca": None}
    try:
        if a["tipo"] == "spy":
            b = spy.iniciar(a["consulta"], a.get("nicho") or None, False, cofre)
            ultima["busca"], ultima["mensagem"] = b["id"], "Busca iniciada. O resultado fica em Spy › Buscas recentes."
        elif a["tipo"] == "tiktok":
            b = tiktok.iniciar(a["consulta"])
            ultima["busca"], ultima["mensagem"] = b["id"], "Busca iniciada. O resultado fica em Spy › TikTok."
        elif a["tipo"] == "youtube":
            if aid in yt_rodando:
                raise ErroAuto("Esta automação já está rodando.")
            yt_rodando.add(aid)
            ultima["status"], ultima["mensagem"] = "rodando", "Buscando os vídeos…"
            ultima["work"] = _registrar(a, ultima)
            threading.Thread(target=_youtube, args=(aid, a, cofre, ultima["quando"], ultima["work"]), daemon=True).start()
    except Exception as e:      # ErroSpy (busca em andamento, Spy não instalado) e o que mais vier
        ultima["status"], ultima["mensagem"] = "erro", str(e)[:300]
    if not ultima.get("work"):
        ultima["work"] = _registrar(a, ultima)
    _anotar(aid, ultima=ultima)
    return ultima


INSTR_RESUMO = """Você resume a transcrição de um vídeo do YouTube para um time de marketing de resposta direta. Responda em português do Brasil, em Markdown, só com isto:
**Ideia central:** uma ou duas frases.
**Gancho:** como o vídeo abre (os primeiros segundos), em uma frase.
**Pontos principais:** de três a seis tópicos curtos.
**O que dá para aproveitar:** uma ou duas frases sobre o ângulo ou o argumento que chama atenção.
Use só o que está na transcrição. Não invente número, nome nem resultado."""


def _youtube(aid, a, cofre, quando, work=None):
    """Busca os vídeos de cada termo e, conforme as opções, baixa, transcreve e resume. No fim grava um relatório em Swipe/YouTube."""
    import agentes
    c, erros, videos, vistos = a["consulta"], [], [], set()
    passo = lambda msg: _anotar(aid, ultima={"quando": quando, "status": "rodando", "mensagem": msg, "busca": None, "work": work})
    try:
        if not cofre or not Path(cofre).is_dir():
            raise ErroAuto("A pasta de arquivos do Octopus IA não está configurada.")
        pasta = Path(cofre) / "Swipe" / "YouTube"
        for termo in c["palavras"]:
            try:
                for v in agentes.buscar_youtube(termo, c["por_termo"], c["formato"]):
                    if v["link"] not in vistos and (v["visualizacoes"] or 0) >= c["min_views"]:
                        vistos.add(v["link"])
                        videos.append({**v, "termo": termo})
            except ValueError as e:
                erros.append(f"{termo}: {e}")
        videos = videos[:40]
        for i, v in enumerate(videos, 1):
            passo(f"Vídeo {i} de {len(videos)}: {v['titulo'][:60]}")
            if c["baixar"]:
                try:
                    v["arquivo"] = agentes.baixar_video(v["link"], cofre)["arquivo"]
                except ValueError as e:
                    erros.append(f"{v['titulo'][:50]}: {e}")
            if c["transcrever"] or c["resumir"]:
                try:
                    v["transcricao"], texto = agentes.transcrever_youtube(v["link"], pasta / "Transcrições")
                    if c["resumir"] and codex is not None:
                        trabalho = LOCAL / "automacoes" / aid
                        trabalho.mkdir(parents=True, exist_ok=True)
                        v["resumo"] = codex.resposta_unica(INSTR_RESUMO, texto[:60000], trabalho).strip()
                except Exception as e:      # vídeo sem legenda e sem áudio, IA sem login ou sem limite: segue para o próximo
                    erros.append(f"{v['titulo'][:50]}: {str(e)[:160]}")
        num = lambda n: f"{n:,}".replace(",", ".") if isinstance(n, int) else "—"
        dur = lambda s: f"{s // 60}:{s % 60:02d}" if isinstance(s, int) else "—"
        cel = lambda t: str(t).replace("|", "/").replace("\n", " ")
        dia = time.strftime("%Y-%m-%d %Hh%M", time.localtime(quando / 1000))
        linhas = ["---", 'tipo: "youtube_relatorio"', f'automacao: {json.dumps(a["nome"], ensure_ascii=False)}', f'data: "{dia[:10]}"',
                  f"videos: {len(videos)}", "---", "", f"# YouTube · {', '.join(c['palavras'])}", "",
                  "| Vídeo | Canal | Visualizações | Duração | Termo |", "|---|---|---|---|---|"]
        linhas += [f"| [{cel(v['titulo'])}]({v['link']}) | {cel(v['canal'])} | {num(v['visualizacoes'])} | {dur(v['segundos'])} | {cel(v['termo'])} |" for v in videos]
        for v in videos:
            if not (v.get("resumo") or v.get("transcricao") or v.get("arquivo")):
                continue
            linhas += ["", f"## {v['titulo']}", f"{v['canal']} · {num(v['visualizacoes'])} visualizações · [abrir no YouTube]({v['link']})", ""]
            if v.get("resumo"):
                linhas += [v["resumo"], ""]
            if v.get("transcricao"):
                linhas.append(f"Transcrição: Swipe/YouTube/Transcrições/{v['transcricao']}")
            if v.get("arquivo"):
                linhas.append(f"Vídeo baixado: Downloads/YouTube/{v['arquivo']}")
        if erros:
            linhas += ["", "## O que não deu certo", ""] + [f"- {e}" for e in erros]
        pasta.mkdir(parents=True, exist_ok=True)
        nota = pasta / (re.sub(r'[/\\:*?"<>|#^\[\]]', " ", f"{dia} - {', '.join(c['palavras'][:2])}")[:90].strip() + ".md")
        nota.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        fim = {"quando": quando, "status": "ok" if videos else "erro", "busca": None, "work": work, "nota": nota.relative_to(cofre).as_posix() if videos else None,
               "mensagem": (f"{len(videos)} vídeos. " + (f"{len(erros)} com problema (veja no relatório)." if erros else "")) if videos
               else ("Nenhum vídeo com esses filtros. " + "; ".join(erros))[:300]}
        _anotar(aid, ultima=fim)
        if work:
            _atualizar_work(work, status=fim["status"], mensagem=fim["mensagem"], nota=fim["nota"], qtd=len(videos))
    except Exception as e:
        _anotar(aid, ultima={"quando": quando, "status": "erro", "mensagem": str(e)[:300], "busca": None, "work": work})
        if work:
            _atualizar_work(work, status="erro", mensagem=str(e)[:300])
    finally:
        yt_rodando.discard(aid)


def vigiar(spy, cofre_fn, cada=30):
    """Roda junto com o servidor e dispara as automações na hora."""
    def laco():
        time.sleep(20)
        while True:
            try:
                for a in _ler():
                    if not a.get("ativa"):
                        continue
                    alvo = _vencimento(a)
                    if not alvo or (a.get("marco") or 0) >= alvo:
                        continue
                    if a["tipo"] == "spy" and (spy.rodando or spy.atual.get("status") in ("rodando", "parando")):
                        continue      # o Spy está ocupado: tenta de novo na próxima volta
                    if a["tipo"] == "tiktok" and tiktok.ocupado():
                        continue
                    if a["tipo"] == "youtube" and yt_rodando:
                        continue
                    _anotar(a["id"], marco=_agora())
                    rodar(a["id"], spy, cofre_fn())
            except Exception:
                pass
            time.sleep(cada)
    threading.Thread(target=laco, daemon=True).start()
