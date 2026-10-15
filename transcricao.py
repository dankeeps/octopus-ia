"""Nó Transcrição do flow: recebe o vídeo, transcreve com o Whisper no computador e grava o .srt
na pasta de arquivos do flow (no cofre, se o projeto está ligado). Uma transcrição por vez
(o Whisper usa a CPU toda); as outras esperam na fila.

O vídeo enviado fica em transcricao/ (na pasta de dados do aplicativo), em <flow>/<nó>/ só até terminar: a cópia é apagada no fim
(o original continua no computador da pessoa).
"""
import json, re, secrets, shutil, subprocess, threading, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
from locais import LOCAL, python_whisper, env_filho
PASTA = LOCAL / "transcricao"
PY = python_whisper()
SCRIPT = RAIZ / "whisper_transcrever.py"
MIDIA = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}
LIMITE = 4 * 1024 ** 3          # 4 GB
VEZ = threading.Lock()          # um Whisper por vez no computador inteiro: nós de Transcrição, aba Transcrição, redes sociais e YouTube


class ErroTranscricao(Exception):
    pass


def ids(flow, no):
    for x in (flow, no):
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,60}", str(x or "")):
            raise ErroTranscricao("identificador inválido")
    return str(flow), str(no)


def nome_midia(nome):
    nome = Path(str(nome or "")).name.strip()
    if not nome or nome.startswith(".") or Path(nome).suffix.lower() not in MIDIA:
        raise ErroTranscricao("Envie um vídeo ou áudio (mp4, mov, mkv, webm, mp3, m4a, wav…).")
    return re.sub(r'[/\\:*?"<>|]', " ", nome)[:120]


class Transcricoes:
    def __init__(self):
        self.lock = threading.Lock()
        self.vez = VEZ                   # um Whisper por vez
        self.jobs = {}                   # (flow, no) -> estado
        self.procs = {}                  # (flow, no) -> processo do Whisper em andamento
        self.cancelados = set()          # pedidos de cancelamento ainda não atendidos

    def instalado(self):
        return PY.exists()

    def estado(self, flow, no):
        with self.lock:
            return {k: v for k, v in (self.jobs.get(ids(flow, no)) or {"status": "nenhum"}).items() if k != "token"}

    def _set(self, chave, token=None, **k):
        """Com token, só mexe se o job ainda for o mesmo: um envio novo no mesmo nó não é atropelado pela thread do envio antigo."""
        with self.lock:
            j = self.jobs.setdefault(chave, {})
            if token is not None and j.get("token") != token:
                return
            j.update(k)

    def cancelar(self, flow, no):
        """Para a transcrição deste nó: se está na fila, sai dela; se está rodando, o Whisper é encerrado. Nada é gravado."""
        chave = ids(flow, no)
        with self.lock:
            st = (self.jobs.get(chave) or {}).get("status")
            if st not in ("na fila", "transcrevendo"):
                return {"status": st or "nenhum"}
            self.cancelados.add(chave)
            p = self.procs.get(chave)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=10)                       # espera o Whisper soltar os arquivos antes de qualquer limpeza
            except subprocess.TimeoutExpired:
                pass
        self._set(chave, status="cancelado", progresso=0, erro=None)
        return {"status": "cancelado"}

    def receber(self, flow, no, nome, tamanho, leitor, destino_dir):
        """Grava o upload em pedaços (sem carregar o vídeo na memória) e põe na fila."""
        chave = ids(flow, no)
        nome = nome_midia(nome)
        if not self.instalado():
            raise ErroTranscricao("O Whisper não está instalado no Octopus IA. Peça ao Claude Code ou ao Codex para rodar a instalação do Octopus IA de novo (instalar.py).")
        if tamanho <= 0 or tamanho > LIMITE:
            raise ErroTranscricao("Arquivo vazio ou maior que 4 GB.")
        with self.lock:
            if (self.jobs.get(chave) or {}).get("status") in ("na fila", "transcrevendo"):
                raise ErroTranscricao("Este nó já está transcrevendo.")
        pasta = PASTA.joinpath(*chave)
        shutil.rmtree(pasta, ignore_errors=True)
        pasta.mkdir(parents=True, exist_ok=True)
        video = pasta / nome
        falta = tamanho
        with open(video, "wb") as f:
            while falta > 0:
                bloco = leitor.read(min(1024 * 1024, falta))
                if not bloco:
                    break
                f.write(bloco)
                falta -= len(bloco)
        if falta > 0:
            shutil.rmtree(pasta, ignore_errors=True)
            raise ErroTranscricao("O envio do vídeo foi interrompido.")
        token = secrets.token_hex(4)
        with self.lock:
            self.cancelados.discard(chave)
            self.jobs[chave] = {"status": "na fila", "video": nome, "progresso": 0, "duracao": None, "erro": None, "arquivo": None, "chars": 0,
                                "inicio": time.time(), "token": token}        # o token diz qual envio é o dono deste nó
        threading.Thread(target=self._rodar, args=(chave, video, destino_dir, token), daemon=True).start()
        return self.estado(*chave)

    def _meu(self, chave, token):
        with self.lock:
            return (self.jobs.get(chave) or {}).get("token") == token

    def _rodar(self, chave, video, destino_dir, token):
        with self.vez:
            if not self._meu(chave, token):                   # o nó já recebeu outro vídeo: esta thread não mexe em nada
                return
            if chave in self.cancelados:                      # cancelado enquanto esperava na fila
                self.cancelados.discard(chave)
                shutil.rmtree(video.parent, ignore_errors=True)
                return
            self._set(chave, token, status="transcrevendo")
            srt = video.with_suffix(".srt")
            try:
                p = subprocess.Popen([str(PY), str(SCRIPT), str(video), str(srt)], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=env_filho(), bufsize=1)
                with self.lock:
                    self.procs[chave] = p
                duracao, idioma = None, None
                for linha in p.stdout:
                    try:
                        ev = json.loads(linha)
                    except ValueError:
                        continue
                    if "duracao" in ev:
                        duracao = ev["duracao"] or None
                        self._set(chave, token, duracao=duracao)
                    elif "t" in ev and duracao:
                        self._set(chave, token, progresso=min(0.99, ev["t"] / duracao))
                    elif ev.get("fim"):
                        idioma = ev.get("idioma")
                erro = p.stderr.read()
                p.wait()
                if chave in self.cancelados:                  # o usuário cancelou: não grava nada
                    return
                if not srt.is_file():      # o Whisper às vezes fecha com erro depois de já ter gravado tudo: o que vale é a legenda existir
                    raise ErroTranscricao("O Whisper não conseguiu transcrever: " + (erro.strip().splitlines() or ["erro desconhecido"])[-1][:200])
                destino_dir.mkdir(parents=True, exist_ok=True)
                base = f"Transcrição - {Path(video).stem}"[:110]
                alvo, i = destino_dir / f"{base}.srt", 2
                while alvo.exists():
                    alvo = destino_dir / f"{base} ({i}).srt"; i += 1
                shutil.move(str(srt), alvo)
                try:                                           # o vídeo fica guardado ao lado da transcrição, com o mesmo nome: é o que deixa ver o texto acompanhando a fala
                    shutil.move(str(video), alvo.with_suffix(Path(video).suffix.lower()))
                except OSError:
                    pass
                texto = alvo.read_text(encoding="utf-8")
                falado = "\n".join(l for l in texto.splitlines() if l.strip() and "-->" not in l and not l.strip().isdigit())
                self._set(chave, token, status="pronto", progresso=1, arquivo=alvo.name, chars=len(falado), idioma=idioma)
            except (ErroTranscricao, OSError) as e:
                self._set(chave, token, status="erro", erro=str(e))
            except Exception as e:                        # qualquer outra falha (ex.: leitura do stdout) não pode deixar o nó preso em "transcrevendo"
                self._set(chave, token, status="erro", erro="A transcrição falhou: " + str(e)[:200])
            finally:
                with self.lock:                           # (sem chamar _meu() aqui dentro: a trava não é reentrante)
                    if self.procs.get(chave) is p:
                        self.procs.pop(chave, None)
                    if (self.jobs.get(chave) or {}).get("token") == token:
                        self.cancelados.discard(chave)
                if self._meu(chave, token):
                    shutil.rmtree(video.parent, ignore_errors=True)      # sobra do envio (em erro ou cancelamento, o vídeo não fica guardado)


def texto_legivel(srt):
    """SRT → linhas "[mm:ss] fala" para mostrar na tela."""
    out = []
    for bloco in re.split(r"\n\s*\n", srt.strip()):
        m = re.search(r"(\d+):(\d+):(\d+)[,.]\d+\s*-->", bloco)
        fala = " ".join(l.strip() for l in bloco.splitlines() if l.strip() and "-->" not in l and not l.strip().isdigit())
        if fala:
            h, mi, s = (int(x) for x in m.groups()) if m else (0, 0, 0)
            out.append((f"[{h * 60 + mi:02d}:{s:02d}] " if m else "") + fala)
    return "\n".join(out)
