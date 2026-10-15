"""Aba Transcrição: transcreve um vídeo ou áudio solto, sem projeto, e guarda para ver depois.

Tudo fica na pasta de arquivos do Octopus IA, em Transcrições/: o vídeo que a pessoa enviou, a legenda
com os tempos (.srt) e uma nota com o texto (.md). Por estar na pasta, aparece no Ficheiro e a pessoa
exclui o que quiser. Se ela excluir o vídeo, a transcrição continua abrindo, só com o texto.
O Whisper roda no computador, um por vez (a mesma fila das transcrições dos flows). Não gasta IA.
"""
import json
import re
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path

import transcricao

PASTA = "Transcrições"
TIPOS = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
         ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".aac": "audio/aac", ".ogg": "audio/ogg", ".flac": "audio/flac"}
AUDIO = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}
trava = threading.Lock()
jobs = {}        # nome-base -> {status, progresso, erro, video, inicio}
procs = {}
cancelados = set()


class ErroTranscritos(Exception):
    pass


def _pasta(v):
    if not v or not Path(v).is_dir():
        raise ErroTranscritos("A pasta de arquivos do Octopus IA não está configurada.")
    return Path(v) / PASTA


def _base_ok(base):
    base = str(base or "")
    if not base or base.startswith(".") or re.search(r'[/\\:*?"<>|]', base) or ".." in base:
        raise ErroTranscritos("transcrição não encontrada")
    return base


def _do_nome(pasta, base):
    """Os arquivos desta transcrição (vídeo, .srt, .md), comparando o nome como texto: glob trataria "[" e "]" do nome como padrão."""
    return sorted(p for p in (pasta.iterdir() if pasta.is_dir() else []) if p.is_file() and p.stem == base)


def _midia(pasta, base):
    """O vídeo ou áudio desta transcrição, se ainda estiver na pasta."""
    for p in _do_nome(pasta, base):
        if p.suffix.lower() in TIPOS:
            return p
    return None


def _seg(t):
    h, m, s = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def segmentos(srt):
    """SRT → [{ini, fim, texto}] com os tempos em segundos."""
    out = []
    for bloco in re.split(r"\n\s*\n", srt.strip()):
        m = re.search(r"(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)", bloco)
        fala = " ".join(l.strip() for l in bloco.splitlines() if l.strip() and "-->" not in l and not l.strip().isdigit())
        if m and fala:
            out.append({"ini": round(_seg(m.group(1)), 2), "fim": round(_seg(m.group(2)), 2), "texto": fala})
    return out


def receber(v, nome, tamanho, leitor, tr):
    """Guarda o vídeo em Transcrições/ (em pedaços, sem carregar na memória) e põe na fila do Whisper."""
    try:
        nome = transcricao.nome_midia(nome)
    except transcricao.ErroTranscricao as e:
        raise ErroTranscritos(str(e))
    if not tr.instalado():
        raise ErroTranscritos("O Whisper não está instalado no Octopus IA. Peça ao Claude Code ou ao Codex para rodar a instalação do Octopus IA de novo (instalar.py).")
    if tamanho <= 0 or tamanho > transcricao.LIMITE:
        raise ErroTranscritos("Arquivo vazio ou maior que 4 GB.")
    pasta = _pasta(v)
    pasta.mkdir(parents=True, exist_ok=True)
    ext = Path(nome).suffix.lower()
    base0 = re.sub(r"\s+", " ", Path(nome).stem).strip()[:100] or "Transcrição"
    base, i = base0, 2
    with trava:
        while base in jobs and jobs[base]["status"] in ("na fila", "transcrevendo") or _do_nome(pasta, base):
            base = f"{base0} ({i})"; i += 1
        token = secrets.token_hex(4)
        cancelados.discard(base)                          # sobra de um cancelamento anterior com este nome
        jobs[base] = {"status": "enviando", "progresso": 0, "erro": None, "video": base + ext, "inicio": time.time(), "token": token}
    video, falta = pasta / (base + ext), tamanho
    try:
        with open(video, "wb") as f:
            while falta > 0:
                bloco = leitor.read(min(1024 * 1024, falta))
                if not bloco:
                    break
                f.write(bloco)
                falta -= len(bloco)
    except OSError as e:
        falta = -1
    if falta != 0:
        video.unlink(missing_ok=True)
        with trava:
            jobs.pop(base, None)
        raise ErroTranscritos("O envio do arquivo foi interrompido.")
    with trava:
        jobs[base]["status"] = "na fila"
    threading.Thread(target=_rodar, args=(base, video, tr, token), daemon=True).start()
    return {"id": base, **{k: v for k, v in jobs[base].items() if k != "token"}}


def _rodar(base, video, tr, token):
    def meu():
        with trava:
            return (jobs.get(base) or {}).get("token") == token
    def set_(**k):
        with trava:
            if (jobs.get(base) or {}).get("token") == token:      # um envio novo com o mesmo nome não é atropelado por esta thread
                jobs[base].update(k)
    with tr.vez:                                      # um Whisper por vez, junto com os dos flows
        if not meu():
            return
        if base in cancelados:
            cancelados.discard(base)
            return
        set_(status="transcrevendo")
        srt = video.with_suffix(".srt")
        try:
            p = subprocess.Popen([str(transcricao.PY), str(transcricao.SCRIPT), str(video), str(srt)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=transcricao.env_filho(), bufsize=1)
            with trava:
                procs[base] = p
            duracao = None
            for linha in p.stdout:
                try:
                    ev = json.loads(linha)
                except ValueError:
                    continue
                if "duracao" in ev:
                    duracao = ev["duracao"] or None
                elif "t" in ev and duracao:
                    set_(progresso=min(0.99, ev["t"] / duracao))
            erro = p.stderr.read()
            p.wait()
            if base in cancelados:
                return
            if not srt.is_file():      # o Whisper às vezes fecha com erro depois de já ter gravado tudo: o que vale é a legenda existir
                raise ErroTranscritos("O Whisper não conseguiu transcrever: " + (erro.strip().splitlines() or ["erro desconhecido"])[-1][:200])
            segs = segmentos(srt.read_text(encoding="utf-8"))
            texto = "\n\n".join(s["texto"] for s in segs)
            video.with_suffix(".md").write_text(
                f'---\ntipo: "transcricao"\narquivo: {json.dumps(video.name, ensure_ascii=False)}\ndata: "{time.strftime("%Y-%m-%d")}"\n'
                f'duracao: {int(segs[-1]["fim"]) if segs else 0}\n---\n# {base}\n\n{texto}\n', encoding="utf-8")
            set_(status="pronto", progresso=1)
        except (ErroTranscritos, OSError) as e:
            set_(status="erro", erro=str(e))
            Path(str(srt) + ".parcial").unlink(missing_ok=True)
        except Exception as e:                            # qualquer outra falha não pode deixar o item preso em "transcrevendo"
            set_(status="erro", erro="A transcrição falhou: " + str(e)[:200])
            Path(str(srt) + ".parcial").unlink(missing_ok=True)
        finally:
            with trava:                                   # (sem chamar meu() aqui dentro: a trava não é reentrante)
                if procs.get(base) is p:
                    procs.pop(base, None)
                if (jobs.get(base) or {}).get("token") == token:
                    cancelados.discard(base)


def cancelar(v, base):
    """Para a transcrição em andamento e tira o arquivo enviado (nada foi transcrito ainda)."""
    base = _base_ok(base)
    with trava:
        st = (jobs.get(base) or {}).get("status")
        if st not in ("na fila", "transcrevendo"):
            return
        cancelados.add(base)
        p = procs.get(base)
        jobs[base].update(status="cancelado", progresso=0)
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=10)                        # espera o Whisper soltar os arquivos antes de apagar
        except subprocess.TimeoutExpired:
            pass
    pasta = _pasta(v)
    m = _midia(pasta, base)
    if m:
        m.unlink(missing_ok=True)
    (pasta / (base + ".srt.parcial")).unlink(missing_ok=True)


def listar(v):
    """As transcrições guardadas (da mais nova para a mais antiga) e as que estão na fila."""
    pasta = _pasta(v)
    out, vistos = [], set()
    for srt in pasta.glob("*.srt") if pasta.is_dir() else []:
        base = srt.stem
        vistos.add(base)
        segs = segmentos(srt.read_text(encoding="utf-8", errors="replace"))
        m = _midia(pasta, base)
        out.append({"id": base, "status": "pronto", "quando": int(srt.stat().st_mtime * 1000), "duracao": int(segs[-1]["fim"]) if segs else 0,
                    "trechos": len(segs), "midia": m.name if m else None, "audio": bool(m and m.suffix.lower() in AUDIO),
                    "comeco": " ".join(s["texto"] for s in segs[:3])[:160]})
    with trava:
        for base, j in jobs.items():
            if base not in vistos and j["status"] in ("enviando", "na fila", "transcrevendo", "erro"):
                vistos.add(base)
                out.append({"id": base, "status": j["status"], "progresso": j.get("progresso") or 0, "erro": j.get("erro"),
                            "quando": int((j.get("inicio") or time.time()) * 1000), "midia": j.get("video")})
    for m in (pasta.iterdir() if pasta.is_dir() else []):         # vídeo sem legenda e sem job: a transcrição foi interrompida (o Octopus IA fechou no meio)
        if m.is_file() and m.suffix.lower() in TIPOS and m.stem not in vistos:
            vistos.add(m.stem)
            out.append({"id": m.stem, "status": "erro", "progresso": 0, "midia": m.name, "quando": int(m.stat().st_mtime * 1000),
                        "erro": "A transcrição foi interrompida: o Octopus IA foi fechado no meio. Exclua este item e envie o vídeo de novo."})
    out.sort(key=lambda x: -x["quando"])
    return out


def abrir(v, base):
    pasta, base = _pasta(v), _base_ok(base)
    srt = pasta / (base + ".srt")
    if not srt.is_file():
        raise ErroTranscritos("transcrição não encontrada")
    m = _midia(pasta, base)
    segs = segmentos(srt.read_text(encoding="utf-8", errors="replace"))
    return {"id": base, "trechos": segs, "midia": m.name if m else None,
            "audio": bool(m and m.suffix.lower() in AUDIO), "nota": f"{PASTA}/{base}.md" if (pasta / (base + ".md")).is_file() else None}


def sincronia_do_flow(pasta, nome_srt):
    """Para o nó de Transcrição de um flow: os trechos com os tempos e se o vídeo ainda está ao lado da legenda."""
    srt = Path(pasta) / nome_srt
    if srt.suffix.lower() != ".srt" or not srt.is_file():
        raise ErroTranscritos("transcrição não encontrada")
    m = _midia(Path(pasta), srt.stem)
    return {"id": srt.stem, "trechos": segmentos(srt.read_text(encoding="utf-8", errors="replace")), "midia": m.name if m else None,
            "audio": bool(m and m.suffix.lower() in AUDIO)}


def midia_do_flow(pasta, nome_srt):
    m = _midia(Path(pasta), Path(nome_srt).stem)
    if not m:
        raise ErroTranscritos("o vídeo não está mais na pasta")
    return m, TIPOS[m.suffix.lower()]


def arquivo_midia(v, base):
    """Caminho e tipo do vídeo/áudio para o servidor entregar ao player."""
    m = _midia(_pasta(v), _base_ok(base))
    if not m:
        raise ErroTranscritos("o arquivo não está mais na pasta")
    return m, TIPOS[m.suffix.lower()]


def excluir(v, local, base):
    """Manda para a lixeira do Octopus IA o vídeo, a legenda e a nota desta transcrição."""
    import ficheiro
    pasta, base = _pasta(v), _base_ok(base)
    cancelar(v, base)                                 # se ainda está na fila ou transcrevendo, para antes de tirar os arquivos
    n = 0
    for p in _do_nome(pasta, base):
        ficheiro.apagar(Path(v), local, f"{PASTA}/{p.name}")
        n += 1
    esquecer_erro(base)
    return n


def esquecer_erro(base):
    with trava:
        if (jobs.get(base) or {}).get("status") in ("erro", "cancelado"):
            jobs.pop(base, None)
