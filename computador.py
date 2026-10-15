"""Acesso de LEITURA às pastas do computador para os chats: listar uma pasta, ler um arquivo de texto e transcrever vídeos e áudios.

Não existe aqui nenhuma função que apague, mova, renomeie ou altere arquivo do usuário: o agente só lê.
Ficam de fora, mesmo para leitura: pastas ocultas (começam com ponto), a pasta Library do sistema e arquivos de chave ou senha.
"""
import hashlib, json, re, subprocess, threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
from locais import LOCAL, python_whisper
PY = python_whisper()
CACHE = LOCAL / "transcricao" / "computador"
MIDIA = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}
TEXTO = {".txt", ".md", ".srt", ".vtt", ".json", ".csv", ".tsv", ".html", ".htm", ".rtf", ".xml", ".yaml", ".yml", ".log"}
SEGREDO = re.compile(r"(^id_(rsa|ed25519|ecdsa))|(\.(pem|key|p12|pfx|keychain|keychain-db|kdbx|gpg|asc)$)|(^\.env)|(senhas?|passwords?)\.", re.I)
_vez = threading.Lock()


class ErroComputador(Exception):
    pass


class SemPermissao(ErroComputador):
    """O macOS bloqueou a pasta para o programa do Octopus IA (privacidade: Downloads, Mesa, Documentos, discos externos)."""
    def __init__(self, caminho):
        self.caminho = str(caminho)
        super().__init__(f"o macOS bloqueou o acesso a {caminho}")


def _protegida(p):
    """A pasta protegida pelo macOS de que o caminho faz parte: (nome na tela, serviço de privacidade, pasta)."""
    casa = Path.home()
    for nome, servico, pasta in (("Downloads", "SystemPolicyDownloadsFolder", casa / "Downloads"), ("Mesa", "SystemPolicyDesktopFolder", casa / "Desktop"),
                                 ("Documentos", "SystemPolicyDocumentsFolder", casa / "Documents")):
        if str(p).casefold() == str(pasta).casefold() or str(p).casefold().startswith(str(pasta).casefold() + "/"):      # "download/x" também é Downloads
            return nome, servico, pasta
    if Path("/Volumes") in p.parents:
        return "o disco externo", "SystemPolicyRemovableVolumes", Path(*p.parts[:3])
    return "esta pasta", None, p if p.is_dir() else p.parent


def _programa():
    """Identificador do programa que roda o servidor (é para ele que o macOS guarda a permissão)."""
    import os, plistlib, sys
    if os.environ.get("OCTOPUS_APP_ID"):                # aberto pelo aplicativo Octopus IA: a permissão é dele, com nome e ícone
        return os.environ["OCTOPUS_APP_ID"]
    exe = Path(sys.executable).resolve()
    extra = Path(sys.base_prefix) / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"      # o python3 da Apple abre este programa por baixo
    for pai in [exe] + list(exe.parents) + ([extra] + list(extra.parents) if extra.exists() else []):
        if pai.suffix == ".app" and (pai / "Contents" / "Info.plist").is_file():
            try:
                return plistlib.loads((pai / "Contents" / "Info.plist").read_bytes()).get("CFBundleIdentifier")
            except Exception:
                return None
    return None


def _acesso(pasta):
    try:
        next(iter(pasta.iterdir()), None)
        return True
    except PermissionError:
        return False
    except OSError:
        return True


def _entrar(caminho):
    """Resolve o caminho e, se ele está numa pasta que o macOS protege e o acesso está bloqueado, avisa com SemPermissao (é o que faz o botão aparecer no chat)."""
    p = _caminho(caminho)
    _, servico, pasta = _protegida(p)
    if servico and not _acesso(pasta):
        raise SemPermissao(pasta)
    try:
        achado = _achar(p)
    except PermissionError:
        raise SemPermissao(pasta)
    _, servico, pasta = _protegida(achado)              # o nome pode ter sido acertado ("download" virou "Downloads"): confere de novo
    if servico and not _acesso(pasta):
        raise SemPermissao(pasta)
    return achado


def permitir(caminho):
    """Chamado pelo botão "Permitir acesso" do chat. Faz o macOS perguntar de novo (a janela de permissão é do próprio sistema, e quem autoriza é a pessoa).
    Se mesmo assim continuar bloqueado, abre os Ajustes do Sistema na tela de privacidade. Devolve {ok, nome, ajustes}."""
    import sys, time
    nome, servico, pasta = _protegida(_caminho(caminho))
    if _acesso(pasta):
        return {"ok": True, "nome": nome}
    if sys.platform != "darwin":
        return {"ok": False, "nome": nome, "ajustes": False}
    import os
    app = Path.home() / "Applications" / "Octopus IA.app"
    if not os.environ.get("OCTOPUS_APP_ID") and app.is_dir():
        # o servidor não foi aberto pelo aplicativo: o macOS não tem a quem pedir a permissão. Reabre pelo aplicativo (ele troca este servidor pelo dele)
        subprocess.Popen(["open", "-n", str(app)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": False, "nome": nome, "reabrindo": True}
    prog = _programa()
    if servico and prog:                               # a resposta antiga ("não permitir") é esquecida, para o sistema perguntar de novo
        subprocess.run(["tccutil", "reset", servico, prog], capture_output=True, timeout=20)
    resultado = {}
    def tentar():
        try:
            next(iter(pasta.iterdir()), None); resultado["ok"] = True
        except OSError:
            resultado["ok"] = False
    t = threading.Thread(target=tentar, daemon=True); t.start(); t.join(90)      # espera a pessoa responder a janela do macOS
    if resultado.get("ok"):
        return {"ok": True, "nome": nome}
    subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_FilesAndFolders"], capture_output=True, timeout=20)
    return {"ok": False, "nome": nome, "ajustes": True}


def _caminho(texto):
    """Resolve o caminho que o agente passou ("Downloads/Pasta X", "~/Desktop", caminho inteiro) e confere se pode ser lido."""
    t = str(texto or "").strip().strip('"')
    if not t:
        raise ErroComputador("diga o caminho")
    casa = Path.home()
    p = Path(t).expanduser()
    if not p.is_absolute():
        p = casa / p
    p = p.resolve()
    permitido = p == casa or casa in p.parents or Path("/Volumes") in p.parents
    partes = p.relative_to(casa).parts if (p == casa or casa in p.parents) else p.parts
    if not permitido or any(x.startswith(".") for x in partes) or (partes[:1] == ("Library",)) or SEGREDO.search(p.name):
        raise ErroComputador("esse caminho não pode ser lido pelo Octopus IA (pasta do sistema, pasta oculta ou arquivo de chave/senha)")
    return p


def _achar(p):
    """Se o caminho não existe, tenta o mesmo nome sem diferenciar maiúsculas, acentos e espaços ("download" acha "Downloads")."""
    if p.exists():
        return p
    plano = lambda s: re.sub(r"[^a-z0-9]", "", "".join(c for c in __import__("unicodedata").normalize("NFD", s.lower()) if __import__("unicodedata").category(c) != "Mn"))
    atual = Path(p.anchor)
    for parte in p.parts[1:]:
        prox = atual / parte
        if not prox.exists() and atual.is_dir():
            cand = [x for x in atual.iterdir() if plano(x.name) == plano(parte)] or [x for x in atual.iterdir() if plano(parte) and plano(x.name).startswith(plano(parte))]
            if len(cand) == 1:
                prox = cand[0]
        atual = prox
    return atual


def listar(caminho):
    p = _entrar(caminho or "~")
    if not p.is_dir():
        raise ErroComputador(f"não achei a pasta {p}. Liste a pasta de cima para ver os nomes certos.")
    pastas, arqs = [], []
    try:
        itens = sorted(p.iterdir(), key=lambda y: y.name.lower())
    except PermissionError:
        raise SemPermissao(p)
    for x in itens:
        if x.name.startswith(".") or SEGREDO.search(x.name):
            continue
        if x.is_dir():
            pastas.append(x.name)
        elif x.is_file():
            ext = x.suffix.lower()
            arqs.append({"nome": x.name, "kb": max(1, x.stat().st_size // 1024), "tipo": "vídeo ou áudio" if ext in MIDIA else "texto" if ext in TEXTO or ext == ".docx" else "outro"})
    return {"pasta": str(p), "pastas": pastas[:300], "arquivos": arqs[:400], "midias": sum(a["tipo"] == "vídeo ou áudio" for a in arqs)}


def ler(caminho):
    p = _entrar(caminho)
    if not p.is_file():
        raise ErroComputador(f"não achei o arquivo {p}")
    ext = p.suffix.lower()
    if ext in MIDIA:
        raise ErroComputador("isso é vídeo ou áudio: use transcrever_do_computador")
    if ext == ".docx":
        import sys
        sys.path.insert(0, str(RAIZ / "ferramentas"))
        import md_docx
        return md_docx.docx_para_md(p)[:200_000]
    if ext not in TEXTO:
        raise ErroComputador("só leio arquivos de texto (.txt, .md, .srt, .vtt, .json, .csv, .html, .docx)")
    if p.stat().st_size > 5_000_000:
        raise ErroComputador("arquivo grande demais para ler de uma vez (mais de 5 MB)")
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:200_000]
    except PermissionError:
        raise SemPermissao(p)


def _chave(p):
    st = p.stat()
    # pelo arquivo em si (nome, tamanho e data), não pelo jeito que o caminho foi escrito: "download/x" e "Downloads/X" são o mesmo vídeo
    return hashlib.sha1(f"{p.name.casefold()}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()


def transcrever(caminho, maximo=8):
    """Transcreve um vídeo/áudio, ou os de uma pasta (até `maximo` novos por chamada; o que já foi transcrito volta na hora).
    Devolve {arquivos: [{nome, duracao, texto}], faltam: quantos ainda não foram transcritos}."""
    p = _entrar(caminho)
    if not p.exists():
        raise ErroComputador(f"não achei {p}")
    midias = [p] if p.is_file() else sorted((x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in MIDIA and not any(y.startswith(".") for y in x.relative_to(p).parts)), key=lambda x: str(x).lower())
    if not midias or (p.is_file() and p.suffix.lower() not in MIDIA):
        raise ErroComputador("não há vídeo nem áudio nesse caminho")
    if not PY.is_file():
        raise ErroComputador("o Whisper não está instalado neste computador")
    CACHE.mkdir(parents=True, exist_ok=True)
    maximo = max(1, min(int(maximo or 8), 12))
    prontos, novos = {}, []
    for m in midias:
        c = CACHE / (_chave(m) + ".json")
        if c.is_file():
            prontos[m] = json.loads(c.read_text(encoding="utf-8"))
        elif len(novos) < maximo:
            novos.append(m)
    if novos:
        with _vez:
            r = subprocess.run([str(PY), str(RAIZ / "whisper_lote.py"), *map(str, novos)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=13 * 60)
        for linha in r.stdout.splitlines():
            try:
                d = json.loads(linha)
            except ValueError:
                continue
            m = Path(d["arq"])
            if d.get("erro"):
                prontos[m] = {"erro": d["erro"]}
            else:
                prontos[m] = {"texto": d["texto"], "duracao": d["duracao"]}
                (CACHE / (_chave(m) + ".json")).write_text(json.dumps(prontos[m], ensure_ascii=False), encoding="utf-8")
    saida = [{"nome": (m.relative_to(p).as_posix() if p.is_dir() else m.name), **prontos[m]} for m in midias if m in prontos]
    return {"pasta": str(p), "total": len(midias), "arquivos": saida, "faltam": len(midias) - len(saida)}
