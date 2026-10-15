#!/usr/bin/env python3
"""Servidor local do Octopus IA: serve a interface, conversa com o Codex e grava no Cérebro (a pasta de arquivos do Octopus IA).

Escuta só em 127.0.0.1. O cofre vem de config.json ("vault"). Toda escrita
fica presa dentro do cofre: nomes com barra, ".." ou caminho absoluto são recusados.
"""
import base64, json, os, re, sys, threading, time, urllib.parse
import agentes, armazem, automacoes, backup, controle, fala as falamod, ficheiro, criativos, encaixe, spy as spymod, tiktok, transcricao, transcritos
from codex_ponte import Codex, ErroCodex
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
FORMATOS_PROTEGIDOS = (RAIZ / "recursos" / "formatos-protegidos").is_file()      # instalação dos alunos: formatos com cadeado
PUBLICO = RAIZ / "prototipo"
from locais import LOCAL, CONFIG
DADOS = LOCAL / "dados"          # projetos, flows e conversas do Octopus IA (não é o cofre)
APP_JSON = DADOS / "app.json"
PORTA = int(os.environ.get("ATLAS_PORTA", "5178"))

# o que cada tipo de documento vira no cofre: pasta dentro do projeto, nome do arquivo e o
# modelo do cofre em que o Codex encaixa o documento antes de gravar
DESTINOS = {
    "biblia": ("VSL", "Bíblia do nicho", "Biblioteca/Modelos/Bíblia do nicho.md"),
    "briefing": ("VSL", "Briefing de tese", "Biblioteca/Modelos/Briefing de tese.md"),
    "cruzamento": ("VSL", "Cruzamento de raio-X", "Biblioteca/Modelos/Cruzamento de raio-X.md"),
}

CODEX = Codex()
SPY = spymod.Spy()
TR = transcricao.Transcricoes()
SOCIAL_TRAVA = threading.Lock()
SOCIAL = {}             # nó Conteúdo das redes sociais: processamentos em andamento (id -> status, progresso, texto)
FALA = falamod.Fala()


TRAVA_APP = threading.Lock()
VERSAO = int(time.time())          # muda a cada gravação; começa diferente a cada vez que o servidor sobe
COPIAS = DADOS / "copias"


def copia_de_seguranca():
    """Antes de gravar por cima, guarda o app.json atual: uma cópia a cada 10 minutos, as 60 últimas (10 horas de uso)."""
    try:
        if not APP_JSON.is_file():
            return
        COPIAS.mkdir(parents=True, exist_ok=True)
        feitas = sorted(COPIAS.glob("app-*.json"))
        if feitas and time.time() - feitas[-1].stat().st_mtime < 600:
            return
        import shutil
        shutil.copy2(APP_JSON, COPIAS / time.strftime("app-%Y%m%d-%H%M%S.json"))
        for velho in feitas[:-59]:
            velho.unlink()
    except OSError:
        pass


def ler_local():
    try:
        return json.loads(APP_JSON.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def montar_estado():
    """Projetos do cofre + os que só existem em app.json, e as configurações."""
    local, v = ler_local(), cofre()
    do_cofre = armazem.carregar(v)
    ids = {p["id"] for p in do_cofre}
    return {"projects": do_cofre + [p for p in local.get("projects") or [] if p.get("id") not in ids], "settings": local.get("settings") or {}}


def estado_atual():
    """O estado como o servidor conhece. Antes do primeiro GET /api/app (ex.: logo depois de reiniciar, com a página ainda aberta)
    lê do disco, em vez de estourar: é daqui que saem a pasta dos arquivos de um flow e as permissões do chat."""
    e = globals().get("ESTADO")
    if e is None:
        e = montar_estado()
        globals()["ESTADO"] = e
    return e


def perms_atuais():
    return agentes.permissoes((estado_atual().get("settings") or {}).get("perms"))


def config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


PASTA_PADRAO = Path.home() / "Octopus IA"       # a pasta de arquivos do app (o Cérebro)
MODELO = Path(__file__).resolve().parent / "cofre-modelo" / "Biblioteca"


def cofre():
    """A pasta onde o Octopus IA guarda tudo. Na primeira vez, ela nasce com a Biblioteca que vem junto com o app."""
    v = Path(config().get("vault") or PASTA_PADRAO).expanduser().resolve()
    if v != PASTA_PADRAO.resolve() and not v.is_dir() and not v.parent.is_dir():
        v = PASTA_PADRAO.resolve()                  # pasta configurada que não existe neste computador: usa a padrão
    if not (v / "Biblioteca").is_dir() and MODELO.is_dir():
        import shutil
        v.mkdir(parents=True, exist_ok=True)
        shutil.copytree(MODELO, v / "Biblioteca")
        (v / "Projetos").mkdir(exist_ok=True)
    if FORMATOS_PROTEGIDOS:
        _formatos_em_dia(v)
    if (v / "Biblioteca" / "Modelos").is_dir() and (MODELO / "Modelos").is_dir():      # modelo novo do app chega a quem já tem a pasta
        for f in (MODELO / "Modelos").glob("*.md"):
            if not (v / "Biblioteca" / "Modelos" / f.name).exists():
                (v / "Biblioteca" / "Modelos" / f.name).write_bytes(f.read_bytes())
    return v


def _formatos_em_dia(v):
    """Instalação dos alunos: a pasta Biblioteca/Formatos é sempre a do programa (os formatos são protegidos e
    mudam de nome entre versões). Se a do aluno estiver diferente, a antiga vai para a lixeira e a nova entra."""
    import shutil, hashlib, time
    origem, destino = MODELO / "Formatos", v / "Biblioteca" / "Formatos"
    if not origem.is_dir() or not (v / "Biblioteca").is_dir():
        return
    marca = hashlib.sha1("\n".join(sorted(p.name for p in origem.glob("*.md"))).encode()).hexdigest()[:12]
    selo = destino / ".versao"
    try:
        if selo.read_text(encoding="utf-8").strip() == marca:
            return
    except OSError:
        pass
    try:
        if destino.exists():
            lixo = v / ".trash" / f"Formatos-{time.strftime('%Y%m%d-%H%M%S')}"
            lixo.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destino), str(lixo))
        shutil.copytree(origem, destino)
        selo.write_text(marca, encoding="utf-8")
    except OSError as e:
        print("Não deu para atualizar os formatos:", e)


def nome_seguro(s, campo):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if not s or s in (".", "..") or re.search(r'[/\\:*?"<>|]', s) or s.startswith("."):
        raise ValueError(f"{campo} inválido: use só letras, números, espaços e hífen.")
    from locais import nome_windows
    s = nome_windows(s[:80])
    if not s:
        raise ValueError(f"{campo} inválido: use só letras, números, espaços e hífen.")
    return s


def projetos_cofre(v):
    """Experts e ofertas que existem no cofre: Projetos/{Expert}/{Oferta}/."""
    base = v / "Projetos" if v else None
    if not base or not base.is_dir():
        return []
    ok = lambda p: p.is_dir() and not p.name.startswith(".")
    return [{"nome": e.name, "ofertas": sorted(o.name for o in e.iterdir() if ok(o) and o.name != "Atlas")}
            for e in sorted(base.iterdir(), key=lambda x: x.name.lower()) if ok(e)]


def dentro(base, alvo):
    try:
        alvo.resolve().relative_to(base)
        return True
    except ValueError:
        return False


class Atlas(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(PUBLICO), **k)

    def log_message(self, fmt, *args):
        sys.stderr.write("[atlas] " + fmt % args + "\n")

    def responder(self, codigo, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def entregar_midia(self, arq, tipo):
        """Entrega um vídeo ou áudio em pedaços, aceitando Range (é o que deixa o player pular para qualquer ponto)."""
        total = arq.stat().st_size
        ini, fim = 0, total - 1
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range") or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                ini = int(m.group(1))
                fim = min(int(m.group(2)), total - 1) if m.group(2) else total - 1
            else:
                ini = max(0, total - int(m.group(2)))
            if ini > fim or ini >= total:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{total}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {ini}-{fim}/{total}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - ini + 1))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            with open(arq, "rb") as f:
                f.seek(ini)
                falta = fim - ini + 1
                while falta > 0:
                    bloco = f.read(min(256 * 1024, falta))
                    if not bloco:
                        break
                    self.wfile.write(bloco)
                    falta -= len(bloco)
        except (BrokenPipeError, ConnectionResetError):
            pass      # o player fechou a conexão para pedir outro trecho: normal

    def origem_local(self):
        o = self.headers.get("Origin")
        if o and not re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", o):
            return False
        return self.headers.get("X-Atlas") == "1"

    def end_headers(self):
        if self.path.split("?")[0].endswith((".html", "/", ".js", ".css")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/api/app":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            global ESTADO
            ESTADO = montar_estado()
            return self.responder(200, {**ESTADO, "versao": VERSAO})
        if not url.path.startswith("/api/") and not (PUBLICO / url.path.lstrip("/")).is_file():
            # rotas do app (/projetos, /p/…): sempre a mesma página; ela lê o endereço e abre a tela certa
            self.path = "/atlas.html"
        if url.path == "/api/versao":             # a versão instalada (o arquivo VERSION, que vem com cada atualização)
            try:
                versao = (RAIZ / "VERSION").read_text(encoding="utf-8").strip()
            except OSError:
                versao = ""
            return self.responder(200, {"versao": versao})
        if url.path == "/api/estado":
            v = cofre()
            ok = bool(v and v.is_dir())
            notas = sum(1 for _ in v.rglob("*.md")) if ok else 0
            return self.responder(200, {"servidor": True, "vault": str(v) if v else None, "existe": ok,
                                        "nome": v.name if v else None, "notas": notas,
                                        "obsidian": ok and (v / ".obsidian").is_dir()})
        if url.path in ("/api/controle", "/api/controle/dados"):
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            v = cofre()
            if not v or not v.is_dir():
                return self.responder(409, {"erro": "Nenhum cofre configurado. Escolha o cofre em Configurações."})
            if url.path == "/api/controle":
                return self.responder(200, {"experts": controle.experts(v)})
            q = urllib.parse.parse_qs(url.query)
            try:
                expert = nome_seguro((q.get("expert") or [""])[0], "")
                oferta = nome_seguro(q["oferta"][0], "") if (q.get("oferta") or [""])[0] else None
            except ValueError as e:
                return self.responder(400, {"erro": str(e)})
            if not expert or not dentro(v, v / "Projetos" / expert / (oferta or "")):
                return self.responder(400, {"erro": "oferta inválida"})
            return self.responder(200, controle.dados(v, expert, oferta, (q.get("base") or [None])[0]))
        if url.path == "/api/chatgpt/limites":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            try:
                return self.responder(200, CODEX.limites())
            except ErroCodex as e:
                return self.responder(502, {"erro": str(e)})
        if url.path == "/api/chatgpt":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            return self.responder(200, CODEX.estado())
        if url.path == "/api/projetos-cofre":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            return self.responder(200, {"experts": projetos_cofre(cofre())})
        if url.path in ("/api/grafo", "/api/nota", "/api/notas", "/api/arvore", "/api/checklist", "/api/remessas"):
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            import indice
            v = cofre()
            q = urllib.parse.parse_qs(url.query)
            if url.path == "/api/grafo":
                return self.responder(200, indice.grafo(v))
            if url.path == "/api/remessas":            # o que a oferta já tem de anúncio: remessas, último número e o próximo
                try:
                    e, o = nome_seguro(q.get("expert", [""])[0], "Expert"), nome_seguro(q.get("oferta", [""])[0], "Oferta")
                except ValueError as err:
                    return self.responder(400, {"erro": str(err)})
                if not dentro(v, v / "Projetos" / e / o):
                    return self.responder(400, {"erro": "caminho fora do cofre"})
                return self.responder(200, criativos.situacao_anuncios(v, e, o))
            if url.path == "/api/checklist":
                try:
                    e = nome_seguro((q.get("expert") or [""])[0], "Expert")
                except ValueError as err:
                    return self.responder(400, {"erro": str(err)})
                if not dentro(v, v / "Projetos" / e) or not (v / "Projetos" / e).is_dir():
                    return self.responder(404, {"erro": "expert não encontrado"})
                return self.responder(200, indice.checklist(v, e))
            if url.path == "/api/arvore":
                return self.responder(200, {"pastas": indice.arvore(v, agentes.SKILLS, MODELO), "protegido": FORMATOS_PROTEGIDOS})
            if url.path == "/api/notas" and q.get("validados"):
                o = v / (q.get("validados") or [""])[0].strip("/")
                return self.responder(200, {"notas": indice.validados(v, o) if dentro(v, o) and o.is_dir() and len(o.relative_to(v).parts) == 3 else []})
            if url.path == "/api/notas":
                return self.responder(200, indice.consultar(v, (q.get("tipo") or [None])[0], (q.get("pasta") or [None])[0], None, (q.get("texto") or [None])[0], 200))
            rel = (q.get("caminho") or [""])[0]
            if rel.startswith("@skill/"):
                n = indice.ler_skill(agentes.SKILLS, rel[7:])
                return self.responder(200, n) if n else self.responder(404, {"erro": "skill não encontrada"})
            if not rel.endswith(".md"):
                rel += ".md"
            if FORMATOS_PROTEGIDOS and rel.replace("\\", "/").lstrip("/").casefold().startswith("biblioteca/formatos/"):
                return self.responder(403, {"erro": "Este formato é protegido.", "protegido": True})
            n = indice.ler(v, rel) if dentro(v, v / rel) else None
            return self.responder(200, n) if n else self.responder(404, {"erro": "nota não encontrada"})
        if url.path in ("/api/personas", "/api/cerebro"):
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            v = cofre()
            if not v or not v.is_dir():
                return self.responder(409, {"erro": "Nenhum cofre configurado. Escolha o cofre em Configurações."})
            q = urllib.parse.parse_qs(url.query)
            try:
                expert = nome_seguro((q.get("expert") or [""])[0], "") if (q.get("expert") or [""])[0] else ""
                oferta = nome_seguro((q.get("oferta") or [""])[0], "") if (q.get("oferta") or [""])[0] else ""
            except ValueError as e:
                return self.responder(400, {"erro": str(e)})
            if url.path == "/api/personas":
                if not expert or not oferta or not dentro(v, v / "Projetos" / expert / oferta):
                    return self.responder(400, {"erro": "diga o expert e a oferta"})
                return self.responder(200, {"personas": criativos.personas(v, expert, oferta)})
            return self.responder(200, agentes.cerebro(v, expert, oferta))
        if url.path == "/api/briefings":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            return self.responder(200, {"briefings": agentes.lista_briefings(cofre())})
        if url.path == "/api/biblias":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            return self.responder(200, {"biblias": agentes.lista_biblias(cofre())})
        if url.path == "/api/transcritos/midia":
            # o player de vídeo não manda o cabeçalho X-Atlas: aqui vale o que o navegador informa (pedido da própria página, nunca de outro site)
            if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none") or (self.headers.get("Origin") and not self.origem_local()):
                return self.responder(403, {"erro": "origem não permitida"})
            try:
                arq, tipo = transcritos.arquivo_midia(cofre(), urllib.parse.parse_qs(url.query).get("id", [""])[0])
            except transcritos.ErroTranscritos as e:
                return self.responder(404, {"erro": str(e)})
            return self.entregar_midia(arq, tipo)
        if url.path.startswith("/api/transcritos"):
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            try:
                if url.path == "/api/transcritos/abrir":
                    return self.responder(200, transcritos.abrir(cofre(), urllib.parse.parse_qs(url.query).get("id", [""])[0]))
                return self.responder(200, {"lista": transcritos.listar(cofre()), "instalado": TR.instalado()})
            except transcritos.ErroTranscritos as e:
                return self.responder(404, {"erro": str(e)})
        if url.path.startswith("/api/tiktok"):
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            try:
                if url.path == "/api/tiktok/busca":
                    return self.responder(200, {"busca": tiktok.busca(urllib.parse.parse_qs(url.query).get("id", [""])[0])})
                return self.responder(200, {"token": tiktok.situacao(), "recentes": tiktok.recentes()})
            except tiktok.ErroTikTok as e:
                return self.responder(404, {"erro": str(e)})
        if url.path == "/api/social/estado":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            j = SOCIAL.get(urllib.parse.parse_qs(url.query).get("id", [""])[0])
            return self.responder(200, j) if j else self.responder(404, {"erro": "processamento não encontrado"})
        if url.path == "/api/automacoes":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            return self.responder(200, {"automacoes": automacoes.listar(), "trabalhos": automacoes.trabalhos(SPY)})
        if url.path == "/api/skills-barra":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            return self.responder(200, {"skills": agentes.skills_barra()})
        if url.path == "/api/modelos":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            try:
                return self.responder(200, {"modelos": CODEX.modelos()})
            except ErroCodex as e:
                return self.responder(502, {"erro": str(e)})
        if url.path.startswith("/api/spy"):
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            q = urllib.parse.parse_qs(url.query)
            try:
                if url.path == "/api/spy":
                    return self.responder(200, SPY.estado(cofre()))
                if url.path == "/api/spy/busca":
                    return self.responder(200, {"busca": SPY.busca(q.get("id", [""])[0], cofre())})
                if url.path == "/api/spy/blacklist":
                    v = cofre()
                    return self.responder(200, {"blacklist": spymod.lista_blacklist(v) if v and v.is_dir() else []})
                if url.path == "/api/spy/atualizacao":
                    return self.responder(200, SPY.atualizacao())
                if url.path == "/api/spy/bibliotecas":
                    v = cofre()
                    return self.responder(200, {"bibliotecas": spymod.bibliotecas(v) if v and v.is_dir() else []})
            except spymod.ErroSpy as e:
                return self.responder(404, {"erro": str(e)})
        if url.path == "/api/transcricao/midia":
            # o player não manda X-Atlas: vale o que o navegador informa (pedido da própria página)
            if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none") or (self.headers.get("Origin") and not self.origem_local()):
                return self.responder(403, {"erro": "origem não permitida"})
            q = urllib.parse.parse_qs(url.query)
            try:
                transcricao.ids(q.get("flow", [""])[0], "nox")
                arq, tipo = transcritos.midia_do_flow(armazem.pasta_arquivos(cofre(), estado_atual(), q.get("flow", [""])[0]), agentes.nome_arquivo(q.get("nome", [""])[0]))
            except (transcritos.ErroTranscritos, transcricao.ErroTranscricao, ValueError) as e:
                return self.responder(404, {"erro": str(e)})
            return self.entregar_midia(arq, tipo)
        if url.path.startswith("/api/transcricao/"):
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            q = urllib.parse.parse_qs(url.query)
            pega = lambda k: q.get(k, [""])[0]
            try:
                if url.path == "/api/transcricao/estado":
                    return self.responder(200, {**TR.estado(pega("flow"), pega("no")), "instalado": TR.instalado()})
                if url.path == "/api/transcricao/sincronia":
                    transcricao.ids(pega("flow"), "nox")
                    try:
                        return self.responder(200, transcritos.sincronia_do_flow(armazem.pasta_arquivos(cofre(), estado_atual(), pega("flow")), agentes.nome_arquivo(pega("nome"))))
                    except transcritos.ErroTranscritos as e:
                        return self.responder(404, {"erro": str(e)})
                if url.path == "/api/transcricao/texto":
                    transcricao.ids(pega("flow"), "nox")
                    nome = agentes.nome_arquivo(pega("nome"))
                    arq = armazem.pasta_arquivos(cofre(), estado_atual(), pega("flow")) / nome
                    if not arq.is_file():
                        return self.responder(404, {"erro": "transcrição não encontrada"})
                    bruto = arq.read_text(encoding="utf-8", errors="replace")
                    return self.responder(200, {"texto": transcricao.texto_legivel(bruto) if nome.lower().endswith(".srt") else bruto})
            except (transcricao.ErroTranscricao, ValueError) as e:
                return self.responder(400, {"erro": str(e)})
        if url.path.startswith("/api/computador/"):      # o Octopus IA só trabalha dentro da pasta dele: o acesso a outras pastas foi desligado
            return self.responder(410, {"erro": "o Octopus IA só trabalha dentro da pasta dele"})
        if url.path == "/api/computador/acesso":
            # só confere se a pasta está liberada (se o macOS ainda não perguntou, é esta leitura que faz a janela aparecer)
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            import computador
            q = urllib.parse.parse_qs(url.query)
            try:
                nome, _, pasta = computador._protegida(computador._caminho((q.get("caminho") or ["Downloads"])[0]))
                return self.responder(200, {"ok": computador._acesso(pasta), "nome": nome, "pelo_app": bool(os.environ.get("OCTOPUS_APP_ID"))})
            except computador.ErroComputador as e:
                return self.responder(400, {"erro": str(e)})
        if url.path == "/api/ficheiro":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            v, local = cofre(), LOCAL
            return self.responder(200, {"itens": ficheiro.listar(v, local), "espaco": ficheiro.espaco(v, local)})
        if url.path == "/api/backup":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            return self.responder(200, backup.estado(CONFIG))
        if url.path == "/api/arquivo":
            if not self.origem_local():
                return self.responder(403, {"erro": "origem não permitida"})
            v = cofre()
            rel = urllib.parse.parse_qs(url.query).get("caminho", [""])[0]
            alvo = (v / rel) if v else None
            if not v or not rel or not alvo or not dentro(v, alvo) or not alvo.is_file() or alvo.suffix != ".md":
                return self.responder(404, {"erro": "arquivo não encontrado no cofre"})
            return self.responder(200, {"caminho": rel, "conteudo": alvo.read_text(encoding="utf-8")})
        return super().do_GET()

    def do_POST(self):
        if not self.origem_local():
            return self.responder(403, {"erro": "origem não permitida"})
        if self.path == "/api/desligar":
            # o atualizador e o atalho pedem para o servidor fechar (para trocar os arquivos do programa com segurança)
            self.responder(200, {"ok": True})
            def fim():
                time.sleep(.3)
                try:
                    if CODEX.proc and CODEX.proc.poll() is None:
                        CODEX.proc.terminate()
                except Exception:
                    pass
                os._exit(0)
            import threading as _th          # (do_POST importa threading mais abaixo: o nome local não serve aqui)
            _th.Thread(target=fim, daemon=True).start()
            return
        if self.path == "/api/fala":
            # ditado do chat: o áudio do microfone vem cru no corpo; devolve o texto falado
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= 30_000_000:
                return self.responder(413, {"erro": "gravação vazia ou longa demais"})
            tipo = (self.headers.get("Content-Type") or "").lower()
            try:
                return self.responder(200, {"texto": FALA.transcrever(self.rfile.read(n), ".m4a" if "mp4" in tipo or "aac" in tipo else ".wav" if "wav" in tipo else ".webm")})
            except falamod.ErroFala as e:
                return self.responder(500, {"erro": str(e)})
        if self.path.startswith("/api/transcritos/enviar"):
            # aba Transcrição: o vídeo vem cru no corpo e fica guardado em Transcrições/, na pasta do Octopus IA
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                tam = int(self.headers.get("Content-Length", "0"))
                return self.responder(200, transcritos.receber(cofre(), q.get("nome", [""])[0], tam, self.rfile, TR))
            except (transcritos.ErroTranscritos, ValueError) as e:
                self.close_connection = True
                return self.responder(400, {"erro": str(e)})
        if self.path.startswith("/api/transcricao/enviar"):
            # vídeo vem cru no corpo (pode ter GBs): grava em pedaços, sem JSON
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            pega = lambda k: q.get(k, [""])[0]
            try:
                transcricao.ids(pega("flow"), pega("no"))
                destino = armazem.pasta_arquivos(cofre(), estado_atual(), pega("flow"))
                tam = int(self.headers.get("Content-Length", "0"))
                return self.responder(200, TR.receber(pega("flow"), pega("no"), pega("nome"), tam, self.rfile, destino))
            except (transcricao.ErroTranscricao, ValueError) as e:
                self.close_connection = True
                return self.responder(400, {"erro": str(e)})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n > 30_000_000:
                return self.responder(413, {"erro": "arquivo grande demais (máximo 20 MB)"})
            dados = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.responder(400, {"erro": "corpo inválido"})
        if self.path == "/api/app":
            if not isinstance(dados, dict) or not isinstance(dados.get("projects"), list):
                return self.responder(400, {"erro": "estado inválido"})
            global ESTADO, VERSAO
            # duas abas (ou dois navegadores) abertas: quem salva com uma versão velha não pode passar por cima do que a outra já gravou.
            # A página recebe 409, junta o que mudou e manda de novo
            with TRAVA_APP:                               # uma gravação por vez: duas ao mesmo tempo embaralhavam as pastas dos flows no cofre
                if dados.get("versao") != VERSAO:
                    return self.responder(409, {"erro": "estado desatualizado", "versao": VERSAO})
                dados.pop("versao", None)
                ESTADO = dados
                v = cofre()
                try:
                    armazem.materializar(v, dados)           # projetos ligados: tudo vira nota no cofre
                except OSError as e:
                    return self.responder(500, {"erro": f"não deu para gravar no cofre: {e}"})
                # só o que não está no cofre fica aqui: projetos sem pasta ligada e as configurações (chaves são segredo)
                local = {"projects": [p for p in dados["projects"] if not armazem.ligado(v, p)], "settings": dados.get("settings") or {}}
                DADOS.mkdir(parents=True, exist_ok=True)
                copia_de_seguranca()
                tmp = APP_JSON.with_suffix(".tmp")
                tmp.write_text(json.dumps(local, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, APP_JSON)          # grava inteiro ou não grava: nunca deixa o arquivo pela metade
                VERSAO += 1
                return self.responder(200, {"ok": True, "salvo": int(time.time()), "versao": VERSAO})
        if self.path == "/api/personas/apagar":
            v = cofre()
            try:
                expert, oferta = nome_seguro(dados.get("expert"), "Expert"), nome_seguro(dados.get("oferta"), "Oferta")
                achou = next((x for x in criativos.personas(v, expert, oferta) if x["nome"] == dados.get("nome")), None) if v else None
                if not achou:
                    raise ValueError("persona não encontrada")
                armazem.para_lixeira(v, v / achou["caminho"])          # some da vista, mas dá para recuperar na lixeira do Octopus IA
                return self.responder(200, {"ok": True})
            except (ValueError, OSError) as e:
                return self.responder(400, {"erro": str(e)})
        if self.path in ("/api/controle/spy", "/api/controle/importar"):
            # o que há no Spy para esta oferta reaproveitar, e trazer (cria atalhos, não copia arquivos)
            v = cofre()
            try:
                expert, oferta = nome_seguro(dados.get("expert"), "Expert"), nome_seguro(dados.get("oferta"), "Oferta")
                if not v or not dentro(v, v / "Projetos" / expert / oferta) or not (v / "Projetos" / expert / oferta).is_dir():
                    raise ValueError("oferta inválida")
                novos = controle.importar(v, expert, oferta, dados.get("anunciante") or None) if self.path.endswith("importar") else 0
                return self.responder(200, {"novos": novos, "spy": controle.no_spy(v, expert, oferta)})
            except (ValueError, OSError, controle.ErroControle) as e:
                return self.responder(400, {"erro": str(e)})
        if self.path == "/api/controle/validar":
            v = cofre()
            try:
                expert, oferta = nome_seguro(dados.get("expert"), "Expert"), nome_seguro(dados.get("oferta"), "Oferta")
                if not v or not dentro(v, controle.pasta(v, expert, oferta)):
                    raise ValueError("oferta inválida")
                return self.responder(200, controle.validar(v, expert, oferta, int(dados.get("n")), bool(dados.get("validado"))))
            except (ValueError, TypeError, controle.ErroControle) as e:
                return self.responder(400, {"erro": str(e)})
        if self.path == "/api/inserir":
            return self.inserir(dados)
        if self.path.startswith("/api/chatgpt/"):
            acao = self.path.rsplit("/", 1)[1]
            try:
                if acao == "entrar":
                    return self.responder(200, CODEX.entrar("chatgptDeviceCode" if dados.get("tipo") == "codigo" else "chatgpt"))
                if acao == "cancelar":
                    return self.responder(200, CODEX.cancelar())
                if acao == "sair":
                    return self.responder(200, CODEX.sair())
            except ErroCodex as e:
                return self.responder(502, {"erro": str(e)})
        if self.path.startswith("/api/computador/"):
            return self.responder(410, {"erro": "o Octopus IA só trabalha dentro da pasta dele"})
        if self.path == "/api/computador/permitir":
            import computador
            try:
                return self.responder(200, computador.permitir(dados.get("caminho")))
            except computador.ErroComputador as e:
                return self.responder(400, {"erro": str(e)})
        if self.path in ("/api/ficheiro/apagar", "/api/ficheiro/esvaziar"):
            v, local = cofre(), LOCAL
            try:
                if self.path.endswith("esvaziar"):
                    ficheiro.esvaziar(v)
                else:
                    ficheiro.apagar(v, local, dados.get("caminho"), MODELO)
            except (ValueError, OSError) as e:
                return self.responder(400, {"erro": str(e)})
            return self.responder(200, {"itens": ficheiro.listar(v, local), "espaco": ficheiro.espaco(v, local, forcar=True)})
        if self.path == "/api/backup/config":
            pasta = str(dados.get("pasta") or "").strip()
            if pasta and not Path(pasta).expanduser().is_dir():
                return self.responder(400, {"erro": "essa pasta não existe neste computador"})
            vezes = int(dados.get("vezes") or 0)
            if vezes not in (0, 1, 2, 3, 7):
                return self.responder(400, {"erro": "frequência inválida"})
            backup.gravar(CONFIG, pasta=str(Path(pasta).expanduser()) if pasta else "", vezes=vezes, erro="")
            return self.responder(200, backup.estado(CONFIG))
        if self.path == "/api/backup/escolher":
            # abre a janela de escolher pasta do próprio sistema (Mac ou Windows). Em outros sistemas, a pessoa cola o caminho
            import subprocess
            if sys.platform == "darwin":
                cmd = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Escolha a pasta do backup do Octopus IA")']
            elif os.name == "nt":
                cmd = ["powershell", "-NoProfile", "-STA", "-Command",
                       "Add-Type -AssemblyName System.Windows.Forms; $f=New-Object System.Windows.Forms.FolderBrowserDialog; "
                       "$f.Description='Escolha a pasta do backup do Octopus IA'; if($f.ShowDialog() -eq 'OK'){ $f.SelectedPath }"]
            else:
                return self.responder(400, {"erro": "neste sistema, cole o caminho da pasta no campo"})
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            except subprocess.TimeoutExpired:
                return self.responder(408, {"erro": "a janela ficou aberta tempo demais"})
            pasta = r.stdout.strip()
            if not pasta:
                return self.responder(200, {"cancelado": True, **backup.estado(CONFIG)})
            backup.gravar(CONFIG, pasta=pasta.rstrip("/\\") or pasta, erro="")
            return self.responder(200, backup.estado(CONFIG))
        if self.path == "/api/backup/agora":
            return self.responder(200, backup.fazer(CONFIG, cofre(), LOCAL))
        if self.path == "/api/projetos-cofre/criar":
            v = cofre()
            if not v or not v.is_dir():
                return self.responder(409, {"erro": "Nenhum cofre configurado. Escolha o cofre em Configurações."})
            try:
                expert = nome_seguro(dados.get("expert"), "Expert")
                oferta = nome_seguro(dados.get("oferta"), "Oferta") if dados.get("oferta") else ""      # projeto = expert; a oferta é opcional
            except ValueError as e:
                return self.responder(400, {"erro": str(e)})
            pasta = v / "Projetos" / expert / oferta
            if not dentro(v, pasta):
                return self.responder(400, {"erro": "caminho fora do cofre"})
            pasta.mkdir(parents=True, exist_ok=True)
            if oferta:                              # a oferta nasce com as pastas padrão, igual à criada pelo chat
                for sub in ("VSL", "Anúncios", "Big ideas", "Controle de mercado", "Personas"):
                    (pasta / sub).mkdir(exist_ok=True)
            import indice
            indice.ficha_do_expert(v, expert)       # todo expert nasce com Credenciais e História, a partir dos modelos
            return self.responder(200, {"expert": expert, "oferta": oferta, "experts": projetos_cofre(v)})
        if self.path == "/api/inteligencia/enviar":
            try:
                agentes.pasta_inteligencia(dados.get("flow"), dados.get("no"))      # valida os ids
                pasta = armazem.pasta_arquivos(cofre(), estado_atual(), dados.get("flow"))
                nome = agentes.nome_arquivo(dados.get("nome"))
                bruto = base64.b64decode(str(dados.get("base64") or ""), validate=True)
            except (ValueError, TypeError) as e:
                return self.responder(400, {"erro": str(e) or "arquivo inválido"})
            if len(bruto) > 20_000_000:
                return self.responder(413, {"erro": "arquivo grande demais (máximo 20 MB)"})
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / nome).write_bytes(bruto)
            info = {"nome": nome, "bytes": len(bruto), "imagem": Path(nome).suffix.lower() in agentes.IMAGEM_EXT}
            if not info["imagem"]:
                info["caracteres"] = len(bruto.decode("utf-8", errors="replace"))
            return self.responder(200, info)
        if self.path == "/api/inteligencia/remover":
            try:
                agentes.pasta_inteligencia(dados.get("flow"), dados.get("no"))
                nome = agentes.nome_arquivo(dados.get("nome"))
            except ValueError as e:
                return self.responder(400, {"erro": str(e)})
            # outro nó do mesmo flow ainda usa este arquivo? então fica
            if not armazem.arquivo_em_uso(estado_atual(), dados.get("flow"), nome, exceto_no=dados.get("no")):
                v = cofre()
                arq = armazem.pasta_arquivos(v, estado_atual(), dados.get("flow")) / nome
                if arq.is_file():
                    if v and armazem.RAIZ not in arq.parents:
                        armazem.para_lixeira(v, arq)
                    else:
                        arq.unlink()
            return self.responder(200, {"ok": True})
        if self.path in ("/api/social/info", "/api/social/transcrever"):
            # nó Conteúdo das redes sociais: lê o link (YouTube, TikTok, Instagram) sem API; a transcrição usa a legenda ou o Whisper
            try:
                if self.path.endswith("info"):
                    return self.responder(200, agentes.info_social(dados.get("url")))
                transcricao.ids(dados.get("flow"), "nox")
                agentes.rede_do_link(dados.get("url"))
                destino = armazem.pasta_arquivos(cofre(), estado_atual(), dados.get("flow"))
                # roda em segundo plano: a tela pergunta o andamento (a porcentagem) até terminar
                import secrets, threading
                jid, url = secrets.token_hex(6), str(dados.get("url"))
                with SOCIAL_TRAVA:
                    SOCIAL[jid] = {"status": "rodando", "progresso": 0.0, "quando": time.time()}

                def trabalho():
                    j = SOCIAL[jid]
                    try:
                        nome, texto = agentes.transcrever_youtube(url, destino, qualquer_rede=True, progresso=lambda p: j.update(progresso=max(j["progresso"], round(p, 3))))
                        corpo = texto.split("\n\n", 1)[1].strip() if "\n\n" in texto else texto
                        if len(corpo) < 3:
                            (destino / nome).unlink(missing_ok=True)
                            j.update(status="sem_fala")
                        else:
                            j.update(status="pronto", progresso=1, arquivo=nome, texto=corpo[:120000])
                    except Exception as e:
                        j.update(status="erro", erro=(str(e) if isinstance(e, ValueError) else "Não deu para processar este vídeo: " + str(e))[:240])
                threading.Thread(target=trabalho, daemon=True).start()
                with SOCIAL_TRAVA:                    # só o que já terminou sai da lista (um vídeo longo pode passar de 2 h rodando)
                    for k in [k for k, x in list(SOCIAL.items()) if x.get("status") != "rodando" and time.time() - x["quando"] > 7200]:
                        SOCIAL.pop(k, None)
                return self.responder(200, {"id": jid})
            except (ValueError, transcricao.ErroTranscricao) as e:
                return self.responder(400, {"erro": str(e)})
            except Exception as e:
                return self.responder(500, {"erro": "Não deu para transcrever este vídeo: " + str(e)[:160]})
        if self.path in ("/api/anexo/renomear", "/api/anexo/excluir"):
            # arquivo do chat (texto colado ou anexo): muda o nome ou apaga de vez a cópia que o agente usa
            try:
                conv = agentes.pasta_conversa(str(dados.get("conversa") or ""))
                for pasta in (conv / "anexos", conv / "anexos_guardados"):      # em chat sem contexto os arquivos antigos ficam guardados à parte
                    arq = pasta / agentes.nome_anexo(dados.get("nome"))
                    if self.path.endswith("excluir"):
                        arq.unlink(missing_ok=True)
                    elif arq.is_file():
                        novo = pasta / agentes.nome_anexo(dados.get("novo"))
                        if novo.exists():
                            return self.responder(400, {"erro": "já existe um arquivo com esse nome nesta conversa"})
                        arq.rename(novo)
            except (ValueError, OSError) as e:
                return self.responder(400, {"erro": str(e)})
            return self.responder(200, {"ok": True})
        if self.path.startswith("/api/transcritos/"):
            acao, tid = self.path.rsplit("/", 1)[1], str(dados.get("id") or "")
            try:
                if acao == "cancelar":
                    transcritos.cancelar(cofre(), tid)
                elif acao == "excluir":
                    transcritos.excluir(cofre(), LOCAL, tid)
                else:
                    return self.responder(404, {"erro": "ação desconhecida"})
                return self.responder(200, {"lista": transcritos.listar(cofre())})
            except (transcritos.ErroTranscritos, ValueError, OSError) as e:
                return self.responder(400, {"erro": str(e)})
        if self.path.startswith("/api/tiktok/"):
            acao, bid = self.path.rsplit("/", 1)[1], str(dados.get("id") or "")
            try:
                if acao == "token":
                    return self.responder(200, {"token": tiktok.guardar_token(dados.get("token"))})
                if acao == "iniciar":
                    return self.responder(200, {"busca": tiktok.iniciar(dados.get("consulta") or {})})
                if acao == "parar":
                    return self.responder(200, {"busca": tiktok.parar(bid)})
                if acao == "apagar":
                    tiktok.apagar(bid)
                    return self.responder(200, {"recentes": tiktok.recentes()})
            except tiktok.ErroTikTok as e:
                return self.responder(400, {"erro": str(e)})
            return self.responder(404, {"erro": "ação desconhecida"})
        if self.path.startswith("/api/automacoes/"):
            acao, aid = self.path.rsplit("/", 1)[1], str(dados.get("id") or "")
            try:
                if acao == "salvar":
                    return self.responder(200, {"automacoes": automacoes.salvar(dados)})
                if acao == "apagar":
                    return self.responder(200, {"automacoes": automacoes.apagar(aid)})
                if acao == "ligar":
                    return self.responder(200, {"automacoes": automacoes.ligar(aid, bool(dados.get("valor")))})
                if acao == "rodar":
                    ultima = automacoes.rodar(aid, SPY, cofre())
                    return self.responder(200, {"ultima": ultima, "automacoes": automacoes.listar(), "trabalhos": automacoes.trabalhos(SPY)})
                if acao == "favoritar":
                    automacoes.favoritar(aid, bool(dados.get("valor")))
                    return self.responder(200, {"trabalhos": automacoes.trabalhos(SPY)})
                if acao == "tirar-trabalho":
                    automacoes.tirar_trabalho(aid)
                    return self.responder(200, {"trabalhos": automacoes.trabalhos(SPY)})
            except automacoes.ErroAuto as e:
                return self.responder(400, {"erro": str(e)})
            return self.responder(404, {"erro": "ação desconhecida"})
        if self.path.startswith("/api/spy/"):
            acao, v, bid = self.path.rsplit("/", 1)[1], cofre(), str(dados.get("id") or "")
            try:
                if acao == "iniciar":
                    return self.responder(200, {"busca": SPY.iniciar(dados.get("consulta") or {}, dados.get("nicho"), bool(dados.get("monitoradas")), v)})
                if acao == "parar":
                    return self.responder(200, {"busca": SPY.parar(bid)})
                if acao == "continuar":
                    return self.responder(200, {"busca": SPY.continuar(bid)})
                if acao == "navegador":
                    return self.responder(200, SPY.abrir_navegador())
                if acao == "monitorar-resultado":
                    caminho = SPY.monitorar_resultado(bid, str(dados.get("rid") or ""), bool(dados.get("valor")), v)
                    return self.responder(200, {"caminho": caminho, "busca": SPY.busca(bid, v)})
                if acao == "gravar":
                    return self.responder(200, SPY.gravar(bid, v))
                if acao == "apagar":
                    SPY.apagar(bid)
                    return self.responder(200, {"ok": True})
                if not v or not v.is_dir():
                    return self.responder(409, {"erro": "Nenhum cofre configurado. Escolha o cofre em Configurações."})
                if acao == "blacklist":
                    spymod.por_na_blacklist(v, str(dados.get("pagina") or ""), str(dados.get("link") or ""), str(dados.get("motivo") or ""))
                    return self.responder(200, {"ok": True})
                if acao == "blacklist-tirar":
                    return self.responder(200, {"saiu": spymod.tirar_da_blacklist(v, str(dados.get("pagina") or ""), str(dados.get("page_id") or ""))})
                if acao == "atualizar":
                    return self.responder(200, SPY.atualizar_monitoradas(v, str(dados.get("nicho") or "") or None))
                if acao == "atualizar-parar":
                    return self.responder(200, SPY.parar_atualizacao())
                if acao == "adicionar":
                    return self.responder(200, SPY.adicionar(dados.get("link"), dados.get("nicho"), v))
                if acao == "editar":
                    caminho = spymod.editar(v, str(dados.get("caminho") or ""), str(dados.get("nome") or ""), str(dados.get("nicho") or ""))
                    return self.responder(200, {"caminho": caminho})
                if acao == "monitorar":
                    spymod.monitorar(v, str(dados.get("caminho") or ""), bool(dados.get("valor")))
                    return self.responder(200, {"ok": True})
            except spymod.ErroSpy as e:
                return self.responder(409, {"erro": str(e)})
            except OSError as e:
                return self.responder(500, {"erro": f"não deu para gravar no cofre: {e}"})
        if self.path == "/api/agente":
            return self.conversar(dados)
        if self.path == "/api/transcricao/cancelar":
            try:
                return self.responder(200, TR.cancelar(str(dados.get("flow") or ""), str(dados.get("no") or "")))
            except (transcricao.ErroTranscricao, ValueError) as e:
                return self.responder(400, {"erro": str(e)})
        if self.path == "/api/agente/parar":
            CODEX.parar(str(dados.get("threadId") or ""))
            return self.responder(200, {"ok": True})
        return self.responder(404, {"erro": "rota desconhecida"})

    def conversar(self, d):
        """Manda a mensagem ao Codex e devolve os eventos em NDJSON, uma linha por evento, enquanto chegam."""
        try:
            # chat sem contexto: os arquivos mandados antes neste chat saem do alcance do agente (ficam guardados à parte, fora das ferramentas).
            # Ele só enxerga o que veio nesta mensagem e o que está ligado nos nós. Com o contexto ligado, eles voltam
            pc = agentes.pasta_conversa(d.get("conversa"))
            visiveis, guardados = pc / "anexos", pc / "anexos_guardados"
            de, para = (visiveis, guardados) if d.get("semContexto") else (guardados, visiveis)
            if de.is_dir():
                para.mkdir(parents=True, exist_ok=True)
                for arq in list(de.iterdir()):
                    if arq.is_file():
                        os.replace(arq, para / arq.name)
            pasta, instr, ferr, execu, anexos = agentes.preparar(d.get("agente"), d.get("conversa"), cofre(), d.get("anexos"), d.get("habilidades"),
                                                                    perms=(estado_atual().get("settings") or {}).get("perms"))
            ctx, imagens = agentes.contexto(d.get("contexto"), pasta, cofre(), estado_atual())
            # o último documento entregue neste chat (para o agente poder gravar no cofre a pedido) e nenhum pedido de gravação antigo
            (pasta / "doc.json").write_text(json.dumps({"tipo": str(d.get("doc") or "")[:40]}), encoding="utf-8")
            (pasta / "inserir.json").unlink(missing_ok=True)
            (pasta / "novos.json").unlink(missing_ok=True)
            (pasta / "permissao.json").unlink(missing_ok=True)
            (pasta / "excluir.json").unlink(missing_ok=True)
            (pasta / "anexos_editados.json").unlink(missing_ok=True)
            (pasta / "blocos_vsl.json").unlink(missing_ok=True)
            texto = "\n\n".join(x for x in [str(d.get("texto") or "").strip(), anexos, ctx, agentes.skill_invocada(d.get("texto"), [d.get("agente")] + [h for h in (d.get("habilidades") or []) if isinstance(h, str)], cofre())] if x)
            if not texto:
                return self.responder(400, {"erro": "mensagem vazia"})
            tid, modelo = CODEX.abrir_thread(d.get("threadId") or None, pasta, instr, ferr, execu, modelo=d.get("modelo") or None)
        except (ValueError, ErroCodex) as e:
            return self.responder(400, {"erro": str(e)})
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def linha(obj):
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")); self.wfile.flush()
        try:
            linha({"tipo": "inicio", "threadId": tid, "modelo": modelo})
            for tipo, valor in CODEX.turno(tid, pasta, texto, modelo, imagens):
                linha({"tipo": tipo, "valor": valor})
            novos = pasta / "novos.json"
            if novos.is_file():                     # arquivos que o agente trouxe (transcrição do YouTube): a tela põe no nó
                linha({"tipo": "arquivos", "valor": json.loads(novos.read_text(encoding="utf-8"))})
                novos.unlink()
            bv = pasta / "blocos_vsl.json"
            if bv.is_file():                        # o agente dividiu a VSL em blocos para medir: a tela marca esses blocos no arquivo da VSL
                linha({"tipo": "blocos_vsl", "valor": json.loads(bv.read_text(encoding="utf-8"))})
                bv.unlink()
            edit = pasta / "anexos_editados.json"
            if edit.is_file():                      # o agente editou um arquivo do chat (dividiu a VSL em blocos): a tela troca o texto do arquivo
                linha({"tipo": "anexos", "valor": json.loads(edit.read_text(encoding="utf-8"))})
                edit.unlink()
            exc = pasta / "excluir.json"
            if exc.is_file():                       # o agente pediu para excluir notas: a tela pergunta "Tem certeza?" e só o clique exclui
                linha({"tipo": "excluir", "valor": json.loads(exc.read_text(encoding="utf-8"))})
                exc.unlink()
            perm = pasta / "permissao.json"
            if perm.is_file():                      # o macOS bloqueou uma pasta: a tela mostra o botão de permitir
                linha({"tipo": "permissao", "valor": json.loads(perm.read_text(encoding="utf-8"))})
                perm.unlink()
            pedido = pasta / "inserir.json"
            if pedido.is_file():                    # o agente pediu para gravar: a tela faz a gravação, com o destino que ele escolheu
                linha({"tipo": "inserir", "valor": json.loads(pedido.read_text(encoding="utf-8"))})
                pedido.unlink()
        except (BrokenPipeError, ConnectionResetError):
            CODEX.parar(tid)

    def inserir(self, d):
        """Encaixa o documento no modelo do cofre (Codex lê o modelo antes) e grava. Responde em NDJSON por etapa."""
        v = cofre()
        if not v or not v.is_dir():
            return self.responder(409, {"erro": "Nenhum cofre configurado. Escolha o cofre em Configurações."})
        if d.get("tipo") not in DESTINOS and d.get("tipo") not in ("anuncio", "bigidea", "controle", "bloco", "dicionario", "persona", "vsl"):
            return self.responder(400, {"erro": "tipo de documento desconhecido"})
        try:
            expert = nome_seguro(d.get("expert"), "Expert")
            oferta = nome_seguro(d.get("oferta"), "Oferta")
        except ValueError as e:
            return self.responder(400, {"erro": str(e)})
        doc = str(d.get("conteudo") or "").strip()
        if not doc:
            return self.responder(400, {"erro": "documento vazio"})
        if d["tipo"] in ("anuncio", "bigidea", "controle", "bloco", "dicionario", "persona", "vsl"):
            # criativos: cada anúncio (ou big idea) vira uma nota, encaixada no modelo do cofre sem passar pela IA
            if not dentro(v, v / "Projetos" / expert / oferta):
                return self.responder(400, {"erro": "caminho fora do cofre"})
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            escrever = lambda obj: (self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")), self.wfile.flush())
            try:
                etapa = lambda t: escrever({"tipo": "etapa", "valor": t})
                pe = perms_atuais()["editar"]            # trocar uma nota que já existe (VSL da versão, dicionário, persona, bloco) é edição: precisa da chave
                r = criativos.gravar_vsl(v, expert, oferta, doc, etapa, pode_editar=pe) if d["tipo"] == "vsl" else criativos.gravar_dicionario(v, expert, oferta, doc, etapa, pode_editar=pe) if d["tipo"] == "dicionario" else criativos.gravar_personas(v, expert, oferta, doc, etapa, pode_editar=pe) if d["tipo"] == "persona" else controle.gravar(v, expert, oferta, doc, etapa) if d["tipo"] == "controle" else criativos.gravar_bloco(v, expert, oferta, doc, etapa, pode_editar=pe) if d["tipo"] == "bloco" else criativos.gravar(v, d["tipo"], expert, oferta, doc, etapa, d.get("remessa") or "nova")
                escrever({"tipo": "fim", "valor": {"caminho": r["caminho"], "obsidian": r["obsidian"], "conteudo": doc, "notas": r["notas"],
                                                   "resumo": r.get("resumo", ""), "avisos": r.get("avisos", [])}})
            except (criativos.ErroCriativos, controle.ErroControle, OSError) as e:
                escrever({"tipo": "erro", "valor": str(e)})
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        pasta_tipo, base, modelo_rel = DESTINOS[d["tipo"]]
        pasta = v / "Projetos" / expert / oferta / pasta_tipo
        modelo_arq = v / modelo_rel
        if not dentro(v, pasta) or not dentro(v, modelo_arq):
            return self.responder(400, {"erro": "caminho fora do cofre"})
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def linha(obj):
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")); self.wfile.flush()
        try:
            linha({"tipo": "etapa", "valor": f"Lendo o modelo do cofre ({modelo_rel})"})
            if not modelo_arq.is_file():
                return linha({"tipo": "erro", "valor": f"O modelo {modelo_rel} não existe no cofre."})
            modelo = modelo_arq.read_text(encoding="utf-8")
            trabalho = agentes.CONVERSAS / "_encaixe"
            # documento que já bate com o modelo é gravado como está, sem passar pela IA (ela poderia mexer nos trechos literais)
            faltas, final = encaixe.conferir(modelo, doc), doc
            for tentativa in ((1, 2) if faltas else ()):
                linha({"tipo": "etapa", "valor": "Encaixando o documento no modelo" if tentativa == 1 else "Corrigindo o que faltou do modelo"})
                final = CODEX.resposta_unica(encaixe.INSTRUCOES, encaixe.pedido(modelo, doc, faltas if tentativa == 2 else None), trabalho)
                linha({"tipo": "etapa", "valor": "Conferindo seções e colunas"})
                faltas = encaixe.conferir(modelo, final)
                if not faltas:
                    break
            if faltas:
                return linha({"tipo": "erro", "valor": "O documento não ficou igual ao modelo. Faltou: " + "; ".join(faltas[:8])})
            final = encaixe.fixar_campos(final, {"expert": expert, "oferta": oferta, "criada": time.strftime("%Y-%m-%d")}, modelo)
            linha({"tipo": "etapa", "valor": "Gravando no cofre"})
            pasta.mkdir(parents=True, exist_ok=True)
            alvo = pasta / f"{base}.md"
            if d.get("modo") != "substituir":
                i = 2
                while alvo.exists():
                    alvo = pasta / f"{base} {i}.md"; i += 1
            elif alvo.exists():
                if not perms_atuais()["editar"]:
                    return linha({"tipo": "erro", "valor": 'A permissão "Editar notas" está desligada em Configurações › Permissões: a nota que já existe não foi substituída.'})
                armazem.para_lixeira(v, alvo)          # nada é perdido: a versão anterior vai para a lixeira do cofre
            alvo.write_text(final, encoding="utf-8")
            rel = alvo.relative_to(v).as_posix()
            link = "obsidian://open?" + urllib.parse.urlencode({"vault": v.name, "file": rel[:-3]}, quote_via=urllib.parse.quote)
            linha({"tipo": "fim", "valor": {"caminho": rel, "obsidian": link, "conteudo": final}})
        except ErroCodex as e:
            linha({"tipo": "erro", "valor": str(e)})
        except (BrokenPipeError, ConnectionResetError):
            pass

if __name__ == "__main__":
    print(f"Octopus IA em http://localhost:{PORTA}  ·  cofre: {cofre()}", flush=True)
    try:
        ThreadingHTTPServer.allow_reuse_address = os.name != "nt"      # no Windows isso deixaria dois servidores na mesma porta
        servidor_http = ThreadingHTTPServer(("127.0.0.1", PORTA), Atlas)
    except OSError as e:
        print(f"A porta {PORTA} já está em uso (outro Octopus IA aberto?). Feche-o e tente de novo. ({e})", flush=True)
        sys.exit(1)
    import shutil as _shutil
    _shutil.rmtree(transcricao.PASTA, ignore_errors=True)     # cópias de vídeo de transcrições que estavam rodando quando o servidor fechou
    backup.vigiar(CONFIG, cofre, LOCAL)
    automacoes.codex = CODEX
    automacoes.vigiar(SPY, cofre)
    servidor_http.serve_forever()
