"""Onde o Octopus IA guarda o que é de cada instalação.

O programa (esta pasta) é trocado a cada atualização. Por isso os dados do aplicativo ficam fora dela:
- Mac: ~/Library/Application Support/Octopus IA
- Windows: %LOCALAPPDATA%\\Octopus IA
- Linux: ~/.local/share/Octopus IA
Ali ficam o login do ChatGPT (codex), as conversas, os flows de projetos sem pasta, o perfil do navegador do Spy,
o ambiente do Whisper, as configurações (config.json) e o registro do servidor.

As notas, os projetos e a Biblioteca ficam na pasta de arquivos do Octopus IA (o Cérebro), em ~/Octopus IA.

Quem já usava uma versão antiga, com os dados em .local dentro do programa, continua com eles lá.
A variável OCTOPUS_DADOS troca o lugar (usada nos testes).
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
WINDOWS = sys.platform == "win32"


def _pasta_dados():
    if os.environ.get("OCTOPUS_DADOS"):
        return Path(os.environ["OCTOPUS_DADOS"]).expanduser()
    if (RAIZ / ".local").is_dir():                       # instalação antiga: os dados já estão ao lado do programa
        return RAIZ / ".local"
    if WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "Octopus IA"


LOCAL = _pasta_dados()
CONFIG = RAIZ / "config.json" if (RAIZ / "config.json").is_file() and LOCAL == RAIZ / ".local" else LOCAL / "config.json"
LOG = LOCAL / "servidor.log"
WHISPER = LOCAL / "whisper"


def python_whisper():
    """O Python do ambiente do Whisper (bin/ no Mac e no Linux, Scripts\\ no Windows)."""
    return WHISPER / ("Scripts" if WINDOWS else "bin") / ("python.exe" if WINDOWS else "python")


def ffmpeg():
    """O ffmpeg que veio com o ambiente do Whisper (pacote imageio-ffmpeg) ou o do sistema. None se não houver."""
    import shutil
    base = WHISPER / ("Lib" if WINDOWS else "lib")
    for p in base.glob("**/imageio_ffmpeg/binaries/ffmpeg*") if base.is_dir() else []:
        if p.is_file() and not p.name.endswith(".md"):
            return str(p)
    return shutil.which("ffmpeg")


def env_filho(**extra):
    """Ambiente para os programas que o Octopus abre (Whisper, yt-dlp, node): tudo em UTF-8, nos dois sistemas."""
    e = dict(os.environ)
    e.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "OCTOPUS_DADOS": str(LOCAL)})
    e.update({k: str(v) for k, v in extra.items()})
    return e


RESERVADOS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def nome_windows(nome):
    """Nome de arquivo ou pasta que também vale no Windows: sem espaço ou ponto no fim, sem nome reservado (CON, NUL…)."""
    nome = str(nome).rstrip(" .")
    if nome.split(".")[0].strip().upper() in RESERVADOS:
        nome = nome + "_"
    return nome


LOCAL.mkdir(parents=True, exist_ok=True)
