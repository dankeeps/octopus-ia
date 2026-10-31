#!/usr/bin/env python3
"""Atualiza o Octopus IA para a versão mais nova, sem mexer nos seus dados.

    python atualizar.py              baixa a versão nova (se houver) e instala
    python atualizar.py --conferir   só diz se há versão nova
    python atualizar.py --forcar     reinstala mesmo que a versão seja a mesma

O que é trocado: os arquivos do programa (esta pasta). Os seus projetos e notas (pasta ~/Octopus IA), o login do
ChatGPT, as conversas e as configurações ficam fora desta pasta e não são tocados. Na primeira abertura depois de
atualizar, a Biblioteca recebe as notas novas: o que você criou fica como está e o que for trocado vai para a lixeira.
De onde vem a versão nova: o repositório público indicado em atualizacao.json.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PROTEGIDOS = {".git", ".local", "config.json", "node_modules"}      # nunca são apagados nem trocados aqui
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except ValueError:
        pass


def baixar(url, tempo=60):
    req = urllib.request.Request(url, headers={"User-Agent": "octopus-ia-atualizador"})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return r.read()


def versao(t):
    return tuple(int(x) for x in t.strip().lstrip("vV").split(".") if x.isdigit())


def main():
    cfg = json.loads((RAIZ / "atualizacao.json").read_text(encoding="utf-8"))
    repo, ramo = cfg["repositorio"], cfg.get("ramo", "main")
    atual = (RAIZ / "VERSION").read_text(encoding="utf-8").strip()
    try:
        nova = baixar(f"https://raw.githubusercontent.com/{repo}/{ramo}/VERSION", 20).decode("utf-8").strip()
    except Exception as e:
        print(f"Não deu para consultar a versão nova (sem internet?): {e}")
        sys.exit(1)
    print(f"Versão instalada: {atual} · versão disponível: {nova}")
    if "--conferir" in sys.argv:
        sys.exit(0)
    if versao(nova) <= versao(atual) and "--forcar" not in sys.argv:
        print("O Octopus IA já está na versão mais nova.")
        sys.exit(0)

    print("Baixando a versão nova…")
    dados = baixar(f"https://github.com/{repo}/archive/refs/heads/{ramo}.zip", 300)
    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(io.BytesIO(dados)).extractall(tmp)
        novo = next(Path(tmp).iterdir())                      # a pasta de dentro do zip (repo-ramo)
        if not (novo / "servidor.py").is_file() or not (novo / "VERSION").is_file():
            print("O pacote baixado não parece o Octopus IA. Nada foi trocado.")
            sys.exit(1)
        print("Desligando o Octopus IA para trocar os arquivos…")
        subprocess.run([sys.executable, str(RAIZ / "ligar.py"), "--parar"])
        for item in novo.iterdir():                           # troca item por item do programa (os protegidos nunca)
            if item.name in PROTEGIDOS:
                continue
            alvo = RAIZ / item.name
            if alvo.is_dir() and not alvo.is_symlink():
                shutil.rmtree(alvo)
            elif alvo.exists() or alvo.is_symlink():
                alvo.unlink()
            shutil.move(str(item), str(alvo))
    print(f"Arquivos trocados para a versão {nova}. Conferindo as dependências…")
    r = subprocess.run([sys.executable, str(RAIZ / "instalar.py"), "--atualizar", "--sem-modelo"])
    notas = RAIZ / "CHANGELOG.md"
    if notas.is_file():
        texto = notas.read_text(encoding="utf-8")
        ini = texto.find(f"## {nova}")
        if ini >= 0:
            fim = texto.find("\n## ", ini + 4)
            print("\nO que mudou:\n" + texto[ini:fim if fim > 0 else None].strip())
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
