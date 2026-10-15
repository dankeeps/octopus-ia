"""Spy no TikTok, pelo Apify (ator clockworks/tiktok-scraper).

A pessoa cola o token do Apify dela em Configurações. O token fica em chaves.json, na pasta de dados do aplicativo, só no
computador: não vai para o cofre, nem para o backup, nem volta para a tela (a tela só sabe que existe).
Cada busca roda o ator com as palavras, espera terminar e guarda os vídeos em spy/tiktok/, na pasta de dados do aplicativo.
O Apify cobra por vídeo devolvido, na conta de quem é dono do token. Não gasta IA.
"""
import json
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
from locais import LOCAL
CHAVES = LOCAL / "chaves.json"
PASTA = LOCAL / "spy" / "tiktok"
ATOR = "clockworks~tiktok-scraper"
API = "https://api.apify.com/v2"
PAISES = {"BR", "PT", "US", "MX", "CO", "ES", "AR", "CL", "PE"}
# o que o ator aceita (conferido no esquema de entrada dele): resultsPerPage de 1 a 1.000.000; ordenação e período são filtros cobrados à parte
ORDENS = ("MOST_RELEVANT", "MOST_LIKED", "LATEST")
PERIODOS = ("ALL_TIME", "PAST_24_HOURS", "PAST_WEEK", "PAST_MONTH", "LAST_3_MONTHS", "LAST_6_MONTHS")
trava = threading.RLock()
buscas = {}


class ErroTikTok(Exception):
    pass


# --- token
def _chaves():
    try:
        d = json.loads(CHAVES.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def token():
    return str(_chaves().get("apify") or "")


def situacao():
    t = token()
    return {"tem": bool(t), "fim": t[-4:] if t else ""}


def guardar_token(t):
    t = str(t or "").strip()
    if t and not re.fullmatch(r"[A-Za-z0-9_\-]{20,200}", t):
        raise ErroTikTok("Esse não parece um token do Apify. Copie em Apify › Settings › API & Integrations.")
    d = _chaves()
    if t:
        d["apify"] = t
    else:
        d.pop("apify", None)
    CHAVES.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHAVES.with_suffix(".tmp")
    tmp.write_text(json.dumps(d), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(CHAVES)
    return situacao()


# --- Apify
def _api(metodo, caminho, corpo=None):
    t = token()
    if not t:
        raise ErroTikTok("Falta o token do Apify. Coloque em Configurações › Integrações.")
    req = urllib.request.Request(API + caminho, method=metodo, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Authorization": "Bearer " + t, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ErroTikTok("O Apify recusou o token. Confira em Configurações › Integrações.")
        if e.code == 402:
            raise ErroTikTok("A conta do Apify está sem crédito para esta busca.")
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise ErroTikTok(f"O Apify respondeu com erro {e.code}. {msg}".strip())
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise ErroTikTok("Não deu para falar com o Apify. Confira a internet e tente de novo.")


def _video(x):
    autor, vid = x.get("authorMeta") or {}, x.get("videoMeta") or {}
    return {"id": str(x.get("id") or ""), "texto": str(x.get("text") or "")[:600], "link": x.get("webVideoUrl") or "",
            "views": x.get("playCount") or 0, "curtidas": x.get("diggCount") or 0, "compart": x.get("shareCount") or 0,
            "coment": x.get("commentCount") or 0, "salvos": x.get("collectCount") or 0,
            "data": x.get("createTimeISO") or "", "autor": autor.get("name") or "", "autor_nome": autor.get("nickName") or "",
            "seguidores": autor.get("fans") or 0, "capa": vid.get("coverUrl") or vid.get("originalCoverUrl") or "",
            "duracao": vid.get("duration") or 0, "palavra": x.get("searchQuery") or "", "anuncio": bool(x.get("isAd"))}


# --- buscas
def _salvar(b):
    PASTA.mkdir(parents=True, exist_ok=True)
    tmp = PASTA / f"{b['id']}.tmp"
    tmp.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PASTA / f"{b['id']}.json")


def _carregar():
    if buscas or not PASTA.is_dir():
        return
    for f in PASTA.glob("*.json"):
        try:
            b = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if b.get("status") == "buscando":
            b["status"], b["mensagem"] = "erro", "O Octopus IA foi fechado durante a busca."
        buscas[b["id"]] = b


def _num(v, pad, lo, hi):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return pad


def iniciar(consulta):
    palavras = []
    for x in consulta.get("palavras") or []:
        x = re.sub(r"\s+", " ", str(x)).strip()[:80]
        if x and x.lower() not in [p.lower() for p in palavras]:
            palavras.append(x)
    if not palavras or len(palavras) > 10:
        raise ErroTikTok("Escolha de uma a dez palavras-chave.")
    pais = str(consulta.get("pais") or "BR").upper()
    if pais not in PAISES:
        pais = "BR"
    c = {"palavras": palavras, "pais": pais, "por_palavra": _num(consulta.get("por_palavra"), 30, 1, 200),
         "min_views": _num(consulta.get("min_views"), 0, 0, 10 ** 9),
         "ordem": consulta.get("ordem") if consulta.get("ordem") in ORDENS else ORDENS[0],
         "periodo": consulta.get("periodo") if consulta.get("periodo") in PERIODOS else PERIODOS[0]}
    entrada = {"searchQueries": palavras, "resultsPerPage": c["por_palavra"], "searchSection": "/video", "proxyCountryCode": pais,
               "shouldDownloadVideos": False, "shouldDownloadCovers": False, "shouldDownloadSlideshowImages": False,
               "shouldDownloadAvatars": False, "shouldDownloadMusicCovers": False, "downloadSubtitlesOptions": "NEVER_DOWNLOAD_SUBTITLES"}
    if c["ordem"] != ORDENS[0]:
        entrada["videoSearchSorting"] = c["ordem"]
    if c["periodo"] != PERIODOS[0]:
        entrada["videoSearchDateFilter"] = c["periodo"]
    with trava:
        _carregar()
        if any(b["status"] == "buscando" for b in buscas.values()):
            raise ErroTikTok("Já tem uma busca do TikTok em andamento.")
        r = _api("POST", f"/acts/{ATOR}/runs", entrada)["data"]
        agora = int(time.time() * 1000)
        b = {"id": secrets.token_hex(4), "status": "buscando", "consulta": c, "corrida": r["id"], "dados": r.get("defaultDatasetId"),
             "videos": [], "mensagem": None, "criada": agora, "atualizada": agora}
        buscas[b["id"]] = b
        _salvar(b)
    threading.Thread(target=_acompanhar, args=(b["id"],), daemon=True).start()
    return b


def _acompanhar(bid):
    b = buscas[bid]
    try:
        for _ in range(240):      # até 20 minutos
            time.sleep(5)
            if b["status"] != "buscando":
                return
            r = _api("GET", f"/actor-runs/{b['corrida']}")["data"]
            if r["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
        itens = _api("GET", f"/datasets/{b['dados']}/items?clean=true&limit=2500")
        vistos, videos = set(), []
        for x in itens if isinstance(itens, list) else []:
            v = _video(x)
            if v["id"] and v["link"] and v["id"] not in vistos:
                vistos.add(v["id"])
                videos.append(v)
        videos.sort(key=lambda v: -v["views"])
        with trava:
            b["videos"] = videos
            b["status"] = "pronta" if videos or r["status"] == "SUCCEEDED" else "erro"
            if b["status"] == "erro":
                b["mensagem"] = "A busca no Apify não terminou bem. Tente de novo."
    except ErroTikTok as e:
        b["status"], b["mensagem"] = "erro", str(e)
    except Exception:
        b["status"], b["mensagem"] = "erro", "A busca parou no meio. Tente de novo."
    b["atualizada"] = int(time.time() * 1000)
    _salvar(b)


def ocupado():
    with trava:
        _carregar()
        return any(b["status"] == "buscando" for b in buscas.values())


def parar(bid):
    with trava:
        b = buscas.get(bid)
        if not b:
            raise ErroTikTok("busca não encontrada")
        if b["status"] == "buscando":
            try:
                _api("POST", f"/actor-runs/{b['corrida']}/abort")
            except ErroTikTok:
                pass
            b["status"], b["mensagem"] = "parada", "Busca parada. Os vídeos já coletados pelo Apify foram cobrados."
            _salvar(b)
    return b


def busca(bid):
    with trava:
        _carregar()
        b = buscas.get(bid)
    if not b:
        raise ErroTikTok("busca não encontrada")
    return b


def recentes():
    with trava:
        _carregar()
        lista = sorted(buscas.values(), key=lambda b: -b["criada"])
    return [{"id": b["id"], "status": b["status"], "palavras": b["consulta"]["palavras"], "videos": len(b["videos"]), "criada": b["criada"]} for b in lista[:30]]


def apagar(bid):
    with trava:
        b = buscas.pop(bid, None)
        if b:
            (PASTA / f"{bid}.json").unlink(missing_ok=True)
