"""Ponte entre o servidor do Octopus IA e o Codex (codex app-server, JSON por stdio).

O Codex roda com um CODEX_HOME só do Octopus IA (codex/, na pasta de dados do aplicativo, permissão 0700): o login do
ChatGPT feito aqui não se mistura com outros usos do Codex, e nenhuma credencial existente
é copiada. Os agentes não recebem shell, edição de arquivo, navegação nem conectores; só as
ferramentas que o próprio Octopus IA registra (ex.: medir_blocos), executadas por este servidor.
"""
import json, os, queue, shutil, subprocess, threading, time, urllib.parse
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
from locais import LOCAL
CODEX_HOME = LOCAL / "codex"
TEMPO_PEDIDO = 30
TEMPO_TURNO = 15 * 60
VALIDADE_LOGIN = 10 * 60

CONFIG_THREAD = {
    "web_search": "disabled",
    "model_provider": "openai",
    "approval_policy": "never",
    "sandbox_mode": "read-only",
    "features": {
        "shell_tool": False, "unified_exec": False, "shell_snapshot": False, "apps": False,
        "multi_agent": False, "multi_agent_v2": False, "browser_use": False,
        "browser_use_external": False, "computer_use": False, "in_app_browser": False,
        "code_mode": False, "code_mode_host": False, "view_image": False, "hooks": False,
        "memories": False, "remote_plugin": False, "skill_mcp_dependency_install": False,
        "image_generation": False,
    },
    "tools": {"view_image": False},
    "mcp_servers": {},
}
PROIBIDOS = {"commandExecution", "fileChange", "mcpToolCall", "webSearch", "collabAgentToolCall"}


class ErroCodex(Exception):
    pass


class Codex:
    def __init__(self, executavel=None):
        self.exe = executavel or os.environ.get("ATLAS_CODEX_BIN") or shutil.which("codex") or "codex"
        self.cmd = [self.exe]
        if os.name == "nt" and self.exe.lower().endswith((".cmd", ".bat")):
            # no Windows o npm instala um atalho .cmd; o Octopus chama o node com o arquivo do Codex direto (sem passar pelo cmd.exe)
            js = Path(self.exe).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
            node = shutil.which("node")
            if js.is_file() and node:
                self.cmd = [node, str(js)]
        self.proc = None
        self.lock = threading.RLock()
        self.lock_tx = threading.Lock()      # uma escrita por vez no stdin do Codex (respostas de ferramenta saem de outras threads)
        self.seq = 0
        self.pendentes = {}          # id -> [Event, resultado, erro]
        self.filas = {}              # threadId -> Queue de notificações
        self.ferramentas = {}        # threadId -> função(nome, argumentos) -> texto
        self.carregadas = set()      # threads abertas neste processo
        self.ativos = {}             # threadId -> turnId em andamento
        self.conta = None
        self.login = None
        self.erro = None

    # ---------- processo ----------
    def _garantir(self):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                return
            CODEX_HOME.mkdir(parents=True, exist_ok=True)
            os.chmod(LOCAL, 0o700); os.chmod(CODEX_HOME, 0o700)
            if os.name == "nt":                      # no Windows o Codex (via node) precisa do ambiente inteiro: SYSTEMROOT, USERPROFILE, APPDATA…
                env = dict(os.environ)
            else:
                env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SHELL") if k in os.environ}
            env["CODEX_HOME"] = str(CODEX_HOME)
            try:
                self.proc = subprocess.Popen(
                    [*self.cmd, "-c", 'cli_auth_credentials_store="file"', "-c", 'forced_login_method="chatgpt"',
                     "app-server", "--listen", "stdio://"],
                    cwd=str(CODEX_HOME), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1)
            except FileNotFoundError:
                self.proc = None
                raise ErroCodex("Codex CLI não encontrado. Instale o Codex e tente de novo.")
            self.carregadas.clear()
            threading.Thread(target=self._ler, args=(self.proc,), daemon=True).start()
            self._pedir("initialize", {"clientInfo": {"name": "octopus-ia", "title": "Octopus IA", "version": "1.0.0"},
                                       "capabilities": {"experimentalApi": True, "requestAttestation": False}})
            self._enviar({"method": "initialized", "params": {}})
            self._ler_conta()

    def _enviar(self, msg):
        p = self.proc
        if not p or p.poll() is not None:
            raise ErroCodex("O Codex não está rodando.")
        try:
            with self.lock_tx:
                p.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n"); p.stdin.flush()
        except (BrokenPipeError, OSError):
            raise ErroCodex("A conexão com o Codex caiu.")

    def _pedir(self, metodo, params=None, tempo=TEMPO_PEDIDO):
        with self.lock:
            self.seq += 1; i = self.seq
            ev = threading.Event(); self.pendentes[i] = [ev, None, None]
            self._enviar({"id": i, "method": metodo, "params": params or {}})
        if not ev.wait(tempo):
            self.pendentes.pop(i, None)
            raise ErroCodex("O Codex demorou para responder.")
        _, res, err = self.pendentes.pop(i)
        if err is not None:
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise ErroCodex(f"O Codex recusou o pedido ({metodo}): {msg}")
        return res

    def _ler(self, proc):
        for linha in proc.stdout:
            try:
                m = json.loads(linha)
            except ValueError:
                continue
            if "id" in m and "method" not in m:
                p = self.pendentes.get(m["id"])
                if p:
                    p[1], p[2] = m.get("result"), m.get("error"); p[0].set()
            elif "id" in m and "method" in m:
                threading.Thread(target=self._responder_pedido, args=(m,), daemon=True).start()
            elif "method" in m:
                self._notificacao(m["method"], m.get("params") or {})
        # processo saiu: libera quem estava esperando
        for p in list(self.pendentes.values()):
            p[2] = {"message": "o Codex encerrou"}; p[0].set()
        for f in list(self.filas.values()):
            f.put(("erro", {"mensagem": "O Codex encerrou no meio da resposta."}))
        self.conta = None

    def _responder_pedido(self, m):
        """Pedidos do Codex para o Octopus IA. Só ferramentas registradas pelo Octopus IA rodam."""
        params = m.get("params") or {}
        if m["method"] == "item/tool/call":
            fn = self.ferramentas.get(params.get("threadId"))
            nome, args = params.get("tool"), params.get("arguments")
            fila = self.filas.get(params.get("threadId"))
            if fila: fila.put(("ferramenta", {"nome": nome + ":" + str(args.get("id") or "").strip().lstrip("#")[:60] if nome == "usar_funcao" and isinstance(args, dict) else nome}))
            try:
                if not fn: raise ErroCodex("ferramenta indisponível")
                texto, ok = fn(nome, args if isinstance(args, dict) else {}), True
            except Exception as e:
                texto, ok = f"Erro: {e}", False
            self._enviar({"id": m["id"], "result": {"success": ok, "contentItems": [{"type": "inputText", "text": texto}]}})
            return
        self._enviar({"id": m["id"], "error": {"code": -32601, "message": "O Octopus IA não permite esta ação."}})
        fila = self.filas.get(params.get("threadId"))
        if fila: fila.put(("bloqueado", {"metodo": m["method"]}))

    def _notificacao(self, metodo, p):
        if metodo in ("account/login/completed", "account/updated"):
            if metodo == "account/login/completed":
                if self.login and p.get("loginId") == self.login["id"]:
                    self.login = None
                    if not p.get("success"):
                        self.erro = "O login não foi concluído. Tente de novo."
            threading.Thread(target=self._ler_conta_seguro, daemon=True).start()
            return
        fila = self.filas.get(p.get("threadId"))
        if fila: fila.put((metodo, p))

    # ---------- conta ----------
    def _ler_conta(self):
        r = self._pedir("account/read", {"refreshToken": False}) or {}
        a = r.get("account")
        self.conta = {"email": a.get("email"), "plano": a.get("planType") or "desconhecido"} if a and a.get("type") == "chatgpt" else None

    def _ler_conta_seguro(self):
        try:
            self._ler_conta(); self.erro = None if self.conta else self.erro
        except ErroCodex as e:
            self.erro = str(e)

    def estado(self):
        try:
            self._garantir()
        except ErroCodex as e:
            return {"disponivel": False, "conectado": False, "erro": str(e)}
        if self.login and time.time() > self.login["expira"]:
            self.cancelar(); self.erro = "O tempo para entrar terminou. Comece de novo."
        return {"disponivel": True, "conectado": bool(self.conta), "conta": self.conta,
                "pendente": {k: v for k, v in (self.login or {}).items() if k != "id"} or None, "erro": self.erro}

    def entrar(self, tipo="chatgpt"):
        self._garantir()
        if self.conta or self.login:
            return self.estado()
        r = self._pedir("account/login/start", {"type": tipo}) or {}
        url = r.get("authUrl") if tipo == "chatgpt" else r.get("verificationUrl")
        host = urllib.parse.urlparse(url or "").hostname
        if not r.get("loginId") or host not in ("auth.openai.com", "chatgpt.com"):
            raise ErroCodex("O Codex devolveu um endereço de login inesperado.")
        self.login = {"id": r["loginId"], "tipo": tipo, "url": url, "codigo": r.get("userCode"),
                      "expira": time.time() + VALIDADE_LOGIN}
        self.erro = None
        return self.estado()

    def cancelar(self):
        if self.login:
            lid, self.login = self.login["id"], None
            try: self._pedir("account/login/cancel", {"loginId": lid})
            except ErroCodex: pass
        return self.estado()

    def sair(self):
        self._garantir(); self.cancelar()
        self._pedir("account/logout"); self._ler_conta()
        return self.estado()

    def limites(self):
        """Quanto do limite do Codex da conta já foi usado. Só leitura: não gasta nada."""
        self._garantir()
        if not self.conta:
            return {"conectado": False, "limites": []}
        r = self._pedir("account/rateLimits/read", {"excludeResetCreditDetails": True}) or {}

        def janela(w):
            if not isinstance(w, dict): return None
            usado = w.get("usedPercent")
            if not isinstance(usado, (int, float)): return None
            return {"usado": max(0.0, min(100.0, float(usado))), "minutos": w.get("windowDurationMins"),
                    "renova": w.get("resetsAt")}

        def bloco(v, rid=None):
            if not isinstance(v, dict): return None
            cr = v.get("credits") if isinstance(v.get("credits"), dict) else None
            jan = [j for j in (janela(v.get("primary")), janela(v.get("secondary"))) if j]
            if not jan and not cr: return None
            return {"id": v.get("limitId") or rid, "nome": v.get("limitName"), "janelas": jan,
                    "creditos": {"tem": cr.get("hasCredits"), "ilimitado": cr.get("unlimited"), "saldo": cr.get("balance")} if cr else None,
                    "travado": bool(v.get("spendControlReached"))}

        blocos = []
        por_id = r.get("rateLimitsByLimitId")
        if isinstance(por_id, dict):
            blocos = [b for b in (bloco(v, k) for k, v in list(por_id.items())[:20]) if b]
        if not blocos:
            b = bloco(r.get("rateLimits"))
            if b: blocos = [b]
        return {"conectado": True, "limites": blocos, "liberado": r.get("ordinaryUsageAllowed"), "lido": int(time.time())}

    # ---------- conversa ----------
    def modelos(self):
        self._garantir()
        if not self.conta: return []
        r = self._pedir("model/list", {"limit": 100, "includeHidden": False}) or {}
        return [{"id": m.get("model") or m.get("id"), "nome": m.get("displayName") or m.get("model") or m.get("id"),
                 "descricao": m.get("description") or "", "padrao": bool(m.get("isDefault"))}
                for m in r.get("data") or [] if not m.get("hidden") and (m.get("model") or m.get("id"))]

    def _modelo(self, pedido=None):
        ms = self.modelos()
        if not ms: raise ErroCodex("Nenhum modelo disponível nesta conta.")
        if pedido and any(m["id"] == pedido for m in ms): return pedido
        return next((m for m in ms if m["padrao"]), ms[0])["id"]

    def abrir_thread(self, thread_id, pasta, instrucoes, ferramentas, executor, efemera=False, modelo=None):
        """Abre (ou reabre) a thread e devolve o id. `executor(nome, args)` roda as ferramentas."""
        self._garantir()
        if not self.conta: raise ErroCodex("Conecte sua conta do ChatGPT em Configurações.")
        pasta.mkdir(parents=True, exist_ok=True)
        base = {"model": self._modelo(modelo), "modelProvider": "openai", "cwd": str(pasta),
                "runtimeWorkspaceRoots": [str(pasta)], "approvalPolicy": "never", "sandbox": "read-only",
                "config": CONFIG_THREAD, "developerInstructions": instrucoes}
        if thread_id and thread_id in self.carregadas:
            self.ferramentas[thread_id] = executor
            return thread_id, base["model"]
        if thread_id:
            r = self._pedir("thread/resume", {**base, "threadId": thread_id, "excludeTurns": True})
        else:
            r = self._pedir("thread/start", {**base, "environments": [], "selectedCapabilityRoots": [],
                                             "dynamicTools": ferramentas, "ephemeral": efemera,
                                             "experimentalRawEvents": False})
        tid = ((r or {}).get("thread") or {}).get("id")
        if not tid: raise ErroCodex("O Codex não abriu a conversa.")
        self.carregadas.add(tid); self.ferramentas[tid] = executor
        return tid, base["model"]

    def turno(self, thread_id, pasta, texto, modelo, imagens=None):
        """Gera os eventos da resposta: ('delta', texto), ('ferramenta', nome), ('fim', texto final), ('erro', msg)."""
        fila = queue.Queue(); self.filas[thread_id] = fila
        mensagens, finais, turno_id = {}, {}, None
        try:
            r = self._pedir("turn/start", {"threadId": thread_id, "model": modelo, "cwd": str(pasta),
                                           "input": [{"type": "text", "text": texto, "text_elements": []}] + [{"type": "localImage", "path": i} for i in (imagens or [])],
                                           "runtimeWorkspaceRoots": [str(pasta)], "approvalPolicy": "never",
                                           "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
                                           "environments": []})
            turno_id = ((r or {}).get("turn") or {}).get("id")
            self.ativos[thread_id] = turno_id
            limite = time.time() + TEMPO_TURNO
            while True:
                try:
                    metodo, p = fila.get(timeout=max(1, limite - time.time()))
                except queue.Empty:
                    self.interromper(thread_id, turno_id)
                    yield ("erro", "A resposta passou do tempo limite."); return
                if metodo == "item/agentMessage/delta" and isinstance(p.get("delta"), str):
                    i = str(p.get("itemId")); mensagens[i] = mensagens.get(i, "") + p["delta"]
                    yield ("delta", p["delta"])
                elif metodo == "item/completed":
                    it = p.get("item") or {}
                    if it.get("type") == "agentMessage" and isinstance(it.get("text"), str) and it.get("phase") != "commentary":
                        finais[str(it.get("id"))] = it["text"]
                elif metodo == "item/started" and (p.get("item") or {}).get("type") in PROIBIDOS:
                    self.interromper(thread_id, turno_id)
                    yield ("erro", "O agente tentou uma ação que o Octopus IA não permite."); return
                elif metodo == "ferramenta":
                    yield ("ferramenta", p.get("nome"))
                elif metodo == "bloqueado":
                    yield ("erro", "O agente pediu uma permissão que o Octopus IA não dá."); return
                elif metodo == "error" and not p.get("willRetry"):
                    e = p.get("error") or {}
                    yield ("erro", (e.get("message") if isinstance(e, dict) else None) or "O Codex falhou nesta resposta."); return
                elif metodo == "erro":
                    yield ("erro", p.get("mensagem")); return
                elif metodo == "turn/completed":
                    t = p.get("turn") or {}
                    if t.get("status") == "failed":
                        err = t.get("error") or {}
                        yield ("erro", (err.get("message") if isinstance(err, dict) else None) or "O Codex falhou nesta resposta."); return
                    texto_final = "\n\n".join(finais.values()) or "\n\n".join(mensagens.values())
                    yield ("fim", texto_final); return
        except ErroCodex as e:
            yield ("erro", str(e))
        finally:
            self.filas.pop(thread_id, None); self.ativos.pop(thread_id, None)

    def resposta_unica(self, instrucoes, texto, pasta):
        """Conversa de uma mensagem só, sem ferramentas, que não fica guardada. Devolve o texto final."""
        tid, modelo = self.abrir_thread(None, pasta, instrucoes, [], None, efemera=True)
        final = None
        try:
            for tipo, valor in self.turno(tid, pasta, texto, modelo):
                if tipo == "fim": final = valor
                elif tipo == "erro": raise ErroCodex(valor)
        finally:
            self.carregadas.discard(tid); self.ferramentas.pop(tid, None)
        return final or ""

    def parar(self, thread_id):
        self.interromper(thread_id, self.ativos.get(thread_id))

    def interromper(self, thread_id, turno_id):
        if turno_id:
            try: self._pedir("turn/interrupt", {"threadId": thread_id, "turnId": turno_id}, tempo=10)
            except ErroCodex: pass
