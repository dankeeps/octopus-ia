#!/usr/bin/env python3
"""Abre o Octopus IA: liga o servidor (se ainda não estiver ligado) e abre a página no navegador.

É o que o ícone da área de trabalho chama, no Mac e no Windows. Não precisa de terminal.
    python ligar.py            liga (ou só abre, se já estiver ligado)
    python ligar.py --parar    desliga o servidor
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from locais import LOCAL, LOG  # noqa: E402

PORTA = int(os.environ.get("ATLAS_PORTA", "5178"))
URL = f"http://localhost:{PORTA}"


def ligado():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/api/versao", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def parar():
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORTA}/api/desligar", data=b"{}", method="POST",
                                     headers={"X-Atlas": "1", "Content-Type": "application/json", "Origin": URL})
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass
    for _ in range(30):
        if not ligado():
            return True
        time.sleep(.2)
    return not ligado()


def subir():
    LOCAL.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "a", encoding="utf-8")
    py = sys.executable
    if os.name == "nt" and py.lower().endswith("pythonw.exe"):
        py = py[:-5] + ".exe" if Path(py[:-5] + ".exe").is_file() else py
    extra = {}
    if os.name == "nt":                         # sem janela de terminal, e o servidor continua depois que o atalho fecha
        extra["creationflags"] = 0x08000000 | 0x00000200      # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    else:
        extra["start_new_session"] = True
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    subprocess.Popen([py, str(RAIZ / "servidor.py")], cwd=str(RAIZ), stdout=log, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, env=env, **extra)
    for _ in range(60):                         # até 15 s para responder
        if ligado():
            return True
        time.sleep(.25)
    return False


def avisar(msg):
    """Sem terminal (atalho), o aviso aparece numa janelinha do sistema."""
    print(msg)
    try:
        if sys.platform == "darwin":
            subprocess.run(["osascript", "-e", f'display alert "Octopus IA" message {json.dumps(msg)}'], timeout=60)
        elif os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "Octopus IA", 0x40)
    except Exception:
        pass


if __name__ == "__main__":
    if "--parar" in sys.argv:
        print("Octopus IA desligado." if parar() else "Não consegui desligar o Octopus IA.")
        sys.exit(0)
    if not ligado() and not subir():
        avisar(f"O Octopus IA não conseguiu ligar. Veja o registro em: {LOG}")
        sys.exit(1)
    if "--sem-navegador" not in sys.argv:
        webbrowser.open(URL)
