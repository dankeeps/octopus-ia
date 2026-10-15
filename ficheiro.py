"""Ficheiro: a lista de todos os arquivos que o Octopus IA guarda e quanto espaço o sistema ocupa.

Excluir manda para a lixeira da pasta de arquivos (.trash). A lixeira só é esvaziada quando a pessoa pede.
"""
import os, shutil, time
from pathlib import Path

_cache = {"quando": 0, "valor": None}


def _tamanho(pasta):
    total = 0
    for raiz, _, arqs in os.walk(pasta):
        for a in arqs:
            try:
                total += os.lstat(os.path.join(raiz, a)).st_size
            except OSError:
                pass
    return total


def espaco(v, local, forcar=False):
    """Bytes por parte: arquivos (a pasta de arquivos), app (flows, conversas, transcrições), lixeira e ferramentas (navegador do Spy, Whisper, login do ChatGPT)."""
    if not forcar and _cache["valor"] and time.time() - _cache["quando"] < 120:
        return _cache["valor"]
    lixeira = _tamanho(v / ".trash") if (v / ".trash").is_dir() else 0
    arquivos = _tamanho(v) - lixeira
    app = sum(_tamanho(local / x) for x in ("dados", "flows", "transcricao", "conversas") if (local / x).is_dir())
    ferramentas = sum(_tamanho(local / x) for x in ("spy", "whisper", "codex") if (local / x).is_dir())
    r = {"arquivos": arquivos, "app": app, "lixeira": lixeira, "ferramentas": ferramentas, "total": arquivos + app + lixeira + ferramentas}
    _cache.update(quando=time.time(), valor=r)
    return r


def listar(v, local):
    """Todos os arquivos: as notas da pasta de arquivos e o que foi enviado nos flows."""
    itens = []
    for p in v.rglob("*"):
        rel = p.relative_to(v)
        if not p.is_file() or any(x.startswith(".") for x in rel.parts) or p.name in (".DS_Store", "Thumbs.db", "desktop.ini"):
            continue
        st = p.stat()
        interno = "Atlas" in rel.parts[:-1]                  # notas internas do app (flows e conversas de projeto ligado)
        itens.append({"caminho": rel.as_posix(), "nome": p.stem if p.suffix == ".md" else p.name, "pasta": rel.parent.as_posix() if rel.parent.as_posix() != "." else "",
                      "area": "Interno do app" if interno else rel.parts[0] if len(rel.parts) > 1 else "Solto", "bytes": st.st_size, "mod": int(st.st_mtime), "nota": p.suffix == ".md" and not interno})
    for base, area in ((local / "flows", "Enviado num flow"), (local / "transcricao", "Transcrição")):
        for p in base.rglob("*") if base.is_dir() else []:
            if p.is_file() and p.name not in (".DS_Store", "Thumbs.db", "desktop.ini"):
                st = p.stat()
                itens.append({"caminho": "@local/" + p.relative_to(local).as_posix(), "nome": p.name, "pasta": area, "area": area, "bytes": st.st_size, "mod": int(st.st_mtime), "nota": False})
    itens.sort(key=lambda x: -x["mod"])
    return itens


def _alvo(v, local, caminho):
    caminho = str(caminho or "")
    base, rel = (local, caminho[7:]) if caminho.startswith("@local/") else (v, caminho)
    if caminho.startswith("@local/") and rel.split("/")[0] not in ("flows", "transcricao"):
        raise ValueError("arquivo fora do ficheiro")
    p = (base / rel).resolve()
    p.relative_to(base.resolve())                       # ValueError se sair da pasta
    if not p.is_file() or any(x.startswith(".") for x in Path(rel).parts):
        raise ValueError("arquivo não encontrado")
    return p


def apagar(v, local, caminho, semente=None):
    """Manda um arquivo ou uma pasta para a lixeira da pasta de arquivos (dá para recuperar até esvaziar).
    Pode: experts, ofertas e o que há dentro; o que está no Spy; as transcrições e os vídeos baixados; e itens da Biblioteca que não vieram com o Octopus IA.
    Não pode: modelos e a biblioteca de base."""
    caminho = str(caminho or "").strip("/")
    if caminho.startswith("@local/"):
        p = _alvo(v, local, caminho)
    else:
        partes = Path(caminho).parts
        if len(partes) < 2 or partes[0] not in ("Projetos", "Swipe", "Biblioteca", "Transcrições", "Downloads") or any(x.startswith(".") or x == ".." for x in partes):
            raise ValueError("isso não pode ser excluído por aqui")
        if partes[0] == "Swipe" and (len(partes) < 3 or (len(partes) == 3 and partes[2] in ("Spy.md", "Blacklist.md"))):
            raise ValueError("essa pasta é do sistema")
        p = (v / caminho).resolve()
        p.relative_to(v.resolve())
        if not p.exists():
            raise ValueError("não encontrei esse item")
        if partes[0] == "Biblioteca":
            if not p.is_file() or partes[1] == "Modelos" or (semente is not None and (semente / Path(*partes[1:])).exists()):
                raise ValueError("faz parte da base do Octopus IA e não pode ser excluído")
    lixo = v / ".trash"; lixo.mkdir(exist_ok=True)
    destino, i = lixo / p.name, 2
    while destino.exists():
        destino = lixo / f"{p.stem} ({i}){p.suffix}"; i += 1
    shutil.move(str(p), str(destino))
    _cache["quando"] = 0


def esvaziar(v):
    """Apaga de vez o que está na lixeira. Só roda quando a pessoa clica em Esvaziar."""
    lixo = v / ".trash"
    for p in lixo.iterdir() if lixo.is_dir() else []:
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    _cache["quando"] = 0
