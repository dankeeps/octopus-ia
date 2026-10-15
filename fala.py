"""Ponte do servidor com o ditado (fala_servico.py): um processo só, que fica aberto depois do primeiro uso."""
import json, subprocess, tempfile, threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
from locais import python_whisper, env_filho
PY = python_whisper()


class ErroFala(Exception):
    pass


class Fala:
    def __init__(self):
        self.trava, self.proc, self.n = threading.Lock(), None, 0

    def transcrever(self, audio, sufixo=".webm"):
        if not PY.is_file():
            raise ErroFala("o Whisper não está instalado neste computador")
        with self.trava:
            if not (self.proc and self.proc.poll() is None):
                self.proc = subprocess.Popen([str(PY), str(RAIZ / "fala_servico.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", env=env_filho())
                if not json.loads(self.proc.stdout.readline() or "{}").get("pronto"):
                    self.proc = None
                    raise ErroFala("o ditado não abriu")
            self.n += 1
            # o arquivo é fechado antes de o outro processo ler (no Windows um arquivo aberto aqui não abre do outro lado)
            f = tempfile.NamedTemporaryFile(suffix=sufixo, delete=False)
            try:
                f.write(audio); f.close()
                try:
                    self.proc.stdin.write(json.dumps({"id": self.n, "arq": f.name}) + "\n"); self.proc.stdin.flush()
                    r = json.loads(self.proc.stdout.readline() or "{}")
                except (OSError, ValueError):
                    self.proc = None
                    raise ErroFala("o ditado parou; tente de novo")
            finally:
                try:
                    Path(f.name).unlink()
                except OSError:
                    pass
            if r.get("erro"):
                raise ErroFala(r["erro"])
            return r.get("texto") or ""
