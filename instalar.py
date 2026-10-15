#!/usr/bin/env python3
"""Instala o Octopus IA neste computador (Mac ou Windows) e cria o ícone na área de trabalho.

    python instalar.py                 instalação completa
    python instalar.py --atualizar     depois de trocar os arquivos por uma versão nova: confere tudo de novo
    python instalar.py --conferir      só mostra o que está instalado e o que falta, sem instalar nada

Opções: --sem-atalho, --sem-modelo (não baixa agora o modelo do Whisper), --sem-spy, --sem-whisper.

Precisa de: Python 3.11 ou mais novo (é este que roda o instalador) e Node.js 18 ou mais novo.
Instala: o Codex (login do ChatGPT), o Whisper (transcrição no computador), o leitor de vídeos (yt-dlp),
o ffmpeg, o navegador do Spy, e cria o atalho. Os dados do aplicativo ficam fora desta pasta (veja locais.py),
então atualizar o programa não apaga nada.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

WIN, MAC = os.name == "nt", sys.platform == "darwin"
ARGS = set(sys.argv[1:])
OK, FALTA = "✓", "✗"
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except ValueError:
        pass


def passo(t):
    print(f"\n== {t}", flush=True)


def rodar(cmd, **k):
    print("   $ " + " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], **k)


def versao_de(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return (r.stdout or r.stderr).strip().splitlines()[0] if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


def parar(msg):
    print(f"\n{FALTA} {msg}\n", flush=True)
    sys.exit(1)


# ---------------------------------------------------------------- requisitos
def conferir_python():
    v = sys.version_info
    if v < (3, 11):
        parar(f"Este Python é o {v.major}.{v.minor}. O Octopus IA precisa do Python 3.11 ou mais novo.\n"
              + ("   No Windows: winget install -e --id Python.Python.3.12  (depois rode com: py -3.12 instalar.py)" if WIN else
                 "   No Mac: brew install python@3.12  (ou o instalador de python.org); depois rode com: python3.12 instalar.py"))
    print(f"   {OK} Python {v.major}.{v.minor}.{v.micro} ({sys.executable})")


def achar_node():
    node = shutil.which("node")
    if not node and MAC:
        node = next((p for p in ("/opt/homebrew/bin/node", "/usr/local/bin/node") if Path(p).exists()), None)
    return node


def conferir_node():
    node = achar_node()
    v = versao_de([node, "--version"]) if node else None
    if not v:
        parar("O Node.js não foi encontrado. Ele é necessário para o login do ChatGPT (Codex) e para o Spy.\n"
              + ("   No Windows: winget install -e --id OpenJS.NodeJS.LTS  (feche e abra o terminal depois)" if WIN else
                 "   No Mac: brew install node  (ou o instalador de nodejs.org)"))
    if int(v.lstrip("v").split(".")[0]) < 18:
        parar(f"O Node.js instalado é o {v}. Precisa do 18 ou mais novo.")
    print(f"   {OK} Node.js {v} ({node})")
    return node


def achar_npm(node):
    npm = shutil.which("npm") or (str(Path(node).parent / ("npm.cmd" if WIN else "npm")) if node else None)
    return npm if npm and Path(npm).exists() else shutil.which("npm")


def instalar_codex(npm):
    codex = shutil.which("codex")
    if codex and versao_de([codex, "--version"]):
        print(f"   {OK} Codex já instalado ({versao_de([codex, '--version'])})")
        return codex
    print("   Instalando o Codex (é por ele que o Octopus IA usa a sua conta do ChatGPT)…")
    r = rodar([npm, "install", "-g", "@openai/codex"])
    codex = shutil.which("codex")
    if WIN and not codex:                      # o npm global do Windows fica em %APPDATA%\npm
        cand = Path(os.environ.get("APPDATA", "")) / "npm" / "codex.cmd"
        codex = str(cand) if cand.is_file() else None
    if r.returncode != 0 or not codex:
        parar("Não deu para instalar o Codex. Rode à mão: npm install -g @openai/codex"
              + ("" if WIN else "  (se der erro de permissão no Mac, instale o Node pelo Homebrew e tente de novo)"))
    print(f"   {OK} Codex instalado")
    return codex


# ---------------------------------------------------------------- whisper, yt-dlp e ffmpeg
def instalar_whisper():
    from locais import WHISPER, python_whisper
    py = python_whisper()
    if not py.is_file():
        print("   Criando o ambiente do Whisper (só na primeira vez)…")
        r = rodar([sys.executable, "-m", "venv", WHISPER])
        if r.returncode != 0 or not py.is_file():
            parar("Não deu para criar o ambiente do Whisper (python -m venv).")
    rodar([py, "-m", "pip", "install", "--upgrade", "pip"], stdout=subprocess.DEVNULL)
    r = rodar([py, "-m", "pip", "install", "--upgrade", "-r", RAIZ / "requisitos-whisper.txt"])
    if r.returncode != 0:
        parar("Não deu para instalar o Whisper (faster-whisper, av, yt-dlp, imageio-ffmpeg). Veja o erro acima.")
    print(f"   {OK} Whisper, leitor de vídeos e ffmpeg instalados")
    if "--sem-modelo" not in ARGS:
        print("   Baixando o modelo de transcrição (cerca de 1,5 GB, só na primeira vez)…")
        modelo = os.environ.get("ATLAS_WHISPER_MODELO", "large-v3-turbo")
        r = rodar([py, "-c", f"from faster_whisper import WhisperModel; WhisperModel({modelo!r}, device='cpu', compute_type='int8'); print('modelo pronto')"])
        if r.returncode != 0:
            print(f"   {FALTA} O modelo não baixou agora (sem internet?). Ele é baixado sozinho na primeira transcrição.")
        else:
            print(f"   {OK} Modelo de transcrição pronto")


# ---------------------------------------------------------------- spy
def instalar_spy(node, npm):
    from locais import LOCAL
    r = rodar([npm, "install", "--omit=dev", "--no-audit", "--no-fund"], cwd=RAIZ)
    if r.returncode != 0:
        print(f"   {FALTA} npm install falhou: o Spy não vai funcionar até isso ser resolvido.")
        return
    env = dict(os.environ, OCTOPUS_DADOS=str(LOCAL))
    r = rodar([node, RAIZ / "spy" / "instalar.mjs"], cwd=RAIZ, env=env)
    print(f"   {OK} Navegador do Spy instalado" if r.returncode == 0 else f"   {FALTA} O navegador do Spy não instalou (veja o erro acima).")


# ---------------------------------------------------------------- atalho
def pythonw():
    """No Windows, o pythonw.exe abre sem janela de terminal."""
    if WIN:
        w = Path(sys.executable).with_name("pythonw.exe")
        return str(w if w.is_file() else sys.executable)
    return sys.executable


def atalho_mac(caminhos_path):
    app = Path.home() / "Applications" / "Octopus IA.app"
    if app.exists():
        shutil.rmtree(app)
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Resources").mkdir(parents=True)
    shutil.copy2(RAIZ / "recursos" / "octopus.icns", app / "Contents" / "Resources" / "octopus.icns")
    (app / "Contents" / "Info.plist").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Octopus IA</string>
  <key>CFBundleDisplayName</key><string>Octopus IA</string>
  <key>CFBundleIdentifier</key><string>br.com.octopusia.app</string>
  <key>CFBundleExecutable</key><string>octopus</string>
  <key>CFBundleIconFile</key><string>octopus</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>{(RAIZ / "VERSION").read_text(encoding="utf-8").strip()}</string>
  <key>LSUIElement</key><true/>
</dict></plist>
""", encoding="utf-8")
    exe = app / "Contents" / "MacOS" / "octopus"
    # o Finder abre o app com um PATH mínimo: o atalho leva junto onde estão o node e o codex
    exe.write_text(f"""#!/bin/bash
export PATH="{':'.join(caminhos_path)}:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
exec "{sys.executable}" "{RAIZ / 'ligar.py'}"
""", encoding="utf-8")
    exe.chmod(0o755)
    mesa = Path.home() / "Desktop" / "Octopus IA.app"
    try:
        if mesa.is_symlink() or mesa.exists():
            mesa.unlink() if mesa.is_symlink() else shutil.rmtree(mesa)
        mesa.symlink_to(app)
    except OSError as e:
        print(f"   {FALTA} Não deu para pôr o atalho na Mesa ({e}). O app está em {app}.")
    subprocess.run(["touch", str(app)])
    print(f"   {OK} App criado em {app} e atalho na Mesa")


def atalho_windows():
    ps = r"""
$d=[Environment]::GetFolderPath('Desktop'); $m=[Environment]::GetFolderPath('Programs')
$w=New-Object -ComObject WScript.Shell
foreach($p in @("$d\Octopus IA.lnk","$m\Octopus IA.lnk")){
  $s=$w.CreateShortcut($p); $s.TargetPath='%PYW%'; $s.Arguments='"%LIGAR%"'; $s.WorkingDirectory='%RAIZ%'
  $s.IconLocation='%ICO%'; $s.Description='Octopus IA'; $s.Save() }
"""
    q = lambda x: str(x).replace("'", "''")            # aspas simples do PowerShell (nome de usuário com apóstrofo)
    ps = ps.replace("%PYW%", q(pythonw())).replace("%LIGAR%", q(RAIZ / "ligar.py")).replace("%RAIZ%", q(RAIZ)).replace("%ICO%", q(RAIZ / "recursos" / "octopus.ico"))
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"   {FALTA} Não deu para criar o atalho: {r.stderr.strip()[:300]}")
    else:
        print(f"   {OK} Atalho criado na área de trabalho e no menu Iniciar")


# ---------------------------------------------------------------- conferência
def conferir_tudo():
    from locais import LOCAL, python_whisper, ffmpeg
    linhas = [
        ("Python 3.11+", sys.version_info >= (3, 11)),
        ("Node.js", bool(achar_node())),
        ("Codex (login do ChatGPT)", bool(shutil.which("codex") or (WIN and (Path(os.environ.get("APPDATA", "")) / "npm" / "codex.cmd").is_file()))),
        ("Whisper", python_whisper().is_file()),
        ("ffmpeg", bool(ffmpeg())),
        ("Spy (playwright)", (RAIZ / "node_modules" / "playwright").is_dir()),
        ("Navegador do Spy", any((LOCAL / "spy" / "browsers").glob("chromium-*/INSTALLATION_COMPLETE")) if (LOCAL / "spy" / "browsers").is_dir() else False),
    ]
    for nome, ok in linhas:
        print(f"   {OK if ok else FALTA} {nome}")
    print(f"   Dados do aplicativo: {LOCAL}")
    print(f"   Arquivos (o Cérebro): {Path.home() / 'Octopus IA'}")
    return all(ok for _, ok in linhas)


def main():
    print(f"Octopus IA {(RAIZ / 'VERSION').read_text(encoding='utf-8').strip()} · {'Windows' if WIN else 'Mac' if MAC else sys.platform}")
    if "--conferir" in ARGS:
        sys.exit(0 if conferir_tudo() else 1)
    passo("1/6 Requisitos")
    conferir_python()
    node = conferir_node()
    npm = achar_npm(node)
    if not npm:
        parar("O npm (que vem com o Node.js) não foi encontrado.")
    passo("2/6 Codex (login do ChatGPT)")
    codex = instalar_codex(npm)
    if "--sem-whisper" not in ARGS:
        passo("3/6 Whisper (transcrição no computador), leitor de vídeos e ffmpeg")
        instalar_whisper()
    if "--sem-spy" not in ARGS:
        passo("4/6 Spy (navegador próprio para a Biblioteca de Anúncios)")
        instalar_spy(node, npm)
    if "--atualizar" in ARGS:                   # o servidor antigo ainda pode estar rodando: desliga para a versão nova subir
        subprocess.run([sys.executable, RAIZ / "ligar.py", "--parar"])
    if "--sem-atalho" not in ARGS:
        passo("5/6 Ícone na área de trabalho")
        if MAC:
            atalho_mac([str(Path(node).parent), str(Path(codex).parent), "/opt/homebrew/bin", "/usr/local/bin"])
        elif WIN:
            atalho_windows()
        else:
            print("   (sem atalho automático neste sistema: abra com  python ligar.py)")
    from locais import LOCAL
    (LOCAL / "instalacao.json").write_text(json.dumps({"versao": (RAIZ / "VERSION").read_text(encoding="utf-8").strip(),
                                                        "python": sys.executable, "pasta": str(RAIZ), "quando": time.strftime("%Y-%m-%d %H:%M")},
                                                       ensure_ascii=False, indent=2), encoding="utf-8")
    passo("6/6 Conferência")
    tudo = conferir_tudo()
    print("\nPronto. Abra o Octopus IA pelo ícone na área de trabalho." if tudo else
          "\nInstalado, mas faltou algo marcado com ✗ acima. Resolva e rode de novo: python instalar.py --atualizar")
    print("No primeiro uso, entre com a sua conta do ChatGPT em Configurações (ou no nó ChatGPT de um flow).")


if __name__ == "__main__":
    main()
