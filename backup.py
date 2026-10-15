"""Backup automático do Octopus IA.

Junta num .zip tudo o que é do usuário e grava na pasta que ele escolheu (em geral, uma pasta do Google Drive
no computador, que o próprio Drive manda para a nuvem):

    Arquivos/      a pasta de arquivos inteira (biblioteca, experts, ofertas, spy), menos a lixeira
    Aplicativo/    projetos, flows e conversas (app.json), arquivos subidos nos flows e transcrições

Nunca entram: o login do ChatGPT, o perfil do navegador do Spy e os programas baixados (codex, spy, whisper).
A frequência é "vezes por semana". Enquanto o servidor está aberto, ele confere sozinho se já é hora.
"""
import datetime, json, os, threading, time, zipfile
from pathlib import Path

GUARDAR = 12                 # quantos backups ficam na pasta (os mais antigos saem)
MAX_ARQ = 50_000_000         # arquivo maior que isso (vídeo) fica de fora
_trava = threading.Lock()


def _cfg(config_arq):
    try:
        return json.loads(config_arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ler(config_arq):
    b = _cfg(config_arq).get("backup") or {}
    return {"pasta": b.get("pasta") or "", "vezes": int(b.get("vezes") or 0), "ultimo": b.get("ultimo") or "", "erro": b.get("erro") or "", "arquivo": b.get("arquivo") or ""}


_trava_cfg = threading.Lock()


def gravar(config_arq, **campos):
    """config.json também guarda o cofre: grava inteiro ou não grava, e uma gravação por vez (a vigia e a tela podem chamar juntas)."""
    with _trava_cfg:
        c = _cfg(config_arq)
        c["backup"] = {**(c.get("backup") or {}), **campos}
        tmp = config_arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, config_arq)
    return ler(config_arq)


def estado(config_arq):
    b = ler(config_arq)
    agora = datetime.datetime.now()
    ult = datetime.datetime.fromisoformat(b["ultimo"]) if b["ultimo"] else None
    prox = (ult + datetime.timedelta(days=7 / b["vezes"])) if ult and b["vezes"] else None
    ligado = bool(b["pasta"] and b["vezes"])
    atrasado = ligado and (ult is None or agora >= prox)
    return {**b, "ligado": ligado, "proximo": prox.isoformat(timespec="minutes") if prox else "", "atrasado": bool(atrasado),
            "pasta_ok": bool(b["pasta"]) and Path(b["pasta"]).expanduser().is_dir()}


def fazer(config_arq, vault, local):
    """Monta o .zip e grava na pasta escolhida. Devolve o estado; em caso de erro, o erro fica registrado."""
    with _trava:
        b = ler(config_arq)
        destino = Path(b["pasta"]).expanduser() if b["pasta"] else None
        try:
            if not destino:
                raise OSError("escolha a pasta do backup primeiro")
            if not destino.is_dir():
                raise OSError(f"a pasta do backup não está disponível: {destino}")
            nome = "Octopus IA backup " + datetime.datetime.now().strftime("%Y-%m-%d %Hh%M") + ".zip"
            tmp = destino / (nome + ".parcial")
            n = 0
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
                def por(base, raiz, pular=()):
                    nonlocal n
                    if not base.exists():
                        return
                    for p in ([base] if base.is_file() else sorted(base.rglob("*"))):
                        rel = p.relative_to(base.parent if base.is_file() else base)
                        if not p.is_file() or any(x in pular for x in rel.parts) or p.stat().st_size > MAX_ARQ or p.name in (".DS_Store", "Thumbs.db", "desktop.ini"):
                            continue
                        if destino in p.parents:                    # a pasta do backup dentro da pasta de arquivos não entra nela mesma
                            continue
                        z.write(p, (Path(raiz) / rel).as_posix()); n += 1
                por(vault, "Arquivos", pular=(".trash",))
                por(local / "dados" / "app.json", "Aplicativo")
                por(local / "flows", "Aplicativo/flows")
                por(local / "transcricao", "Aplicativo/transcricao")
            tmp.replace(destino / nome)
            antigos = sorted(destino.glob("Octopus IA backup *.zip"))[:-GUARDAR]
            for a in antigos:
                a.unlink()
            gravar(config_arq, ultimo=datetime.datetime.now().isoformat(timespec="seconds"), erro="", arquivo=nome, itens=n)
        except (OSError, zipfile.BadZipFile) as e:
            gravar(config_arq, erro=str(e))
        return estado(config_arq)


def vigiar(config_arq, vault_fn, local, cada=600):
    """Roda junto com o servidor: a cada 10 minutos confere se o backup está na hora e faz."""
    def laco():
        time.sleep(30)
        while True:
            try:
                if estado(config_arq)["atrasado"]:
                    fazer(config_arq, vault_fn(), local)
            except Exception:
                pass
            time.sleep(cada)
    threading.Thread(target=laco, daemon=True).start()
