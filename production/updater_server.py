"""HTTP updater sidecar — recebe pedidos do Django e executa o pipeline
de atualização do stack via Docker socket.

Endpoints:
  GET  /health            → 200 "OK"
  GET  /status            → estado do último job (success/failed/running)
  POST /update            → inicia novo update em background; devolve job_id
                           Header obrigatório: X-Updater-Secret

Variáveis de ambiente:
  UPDATER_SECRET     → token obrigatório no header X-Updater-Secret
  COMPOSE_PROJECT    → nome do projecto compose (ex: appleguasfranzinaspt)
  COMPOSE_FILE_PATH  → caminho do compose file (default: /repo/production/docker-compose.yml)
  BRANCH             → branch git a actualizar (default: main)
  REPO_PATH          → onde o repo está montado (default: /repo)

Segurança: o secret é o único gate. Container tem acesso ao Docker socket.
Manter na rede interna leguas_net (não expor porta no host).
"""
import json
import os
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET = os.environ.get("UPDATER_SECRET", "")
PROJECT = os.environ.get("COMPOSE_PROJECT", "appleguasfranzinaspt")
COMPOSE_FILE = os.environ.get(
    "COMPOSE_FILE_PATH", "/repo/production/docker-compose.yml",
)
BRANCH = os.environ.get("BRANCH", "main")
REPO = os.environ.get("REPO_PATH", "/repo")

# Estado partilhado entre threads — guardado em memória + ficheiro
STATE_FILE = "/tmp/updater_state.json"
_lock = threading.Lock()


def _save_state(state):
    with _lock:
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(state, f)
        except OSError:
            pass


def _load_state():
    with _lock:
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"phase": "idle", "job_id": None, "steps": []}


def _run(cmd, cwd=None, timeout=900):
    """Executa um comando shell, devolve dict com rc/stdout/stderr."""
    started = time.time()
    try:
        p = subprocess.run(
            cmd, shell=True, cwd=cwd or REPO, timeout=timeout,
            capture_output=True, text=True,
        )
        return {
            "cmd": cmd,
            "rc": p.returncode,
            "stdout": (p.stdout or "")[-4000:],
            "stderr": (p.stderr or "")[-4000:],
            "duration": round(time.time() - started, 2),
        }
    except subprocess.TimeoutExpired:
        return {
            "cmd": cmd, "rc": -1,
            "stderr": f"timeout após {timeout}s",
            "duration": round(time.time() - started, 2),
        }
    except Exception as e:
        return {
            "cmd": cmd, "rc": -1, "stderr": str(e),
            "duration": round(time.time() - started, 2),
        }


def _update_pipeline(job_id):
    """Executa o pipeline de update em background.

    Plano:
      1. git fetch + git reset --hard origin/{branch}
      2. docker compose build web
      3. docker compose up -d --no-deps --force-recreate web celery_worker celery_beat
      4. esperar healthcheck do web
    """
    state = {
        "phase": "running",
        "job_id": job_id,
        "started_at": time.time(),
        "steps": [],
        "current_step": "git fetch",
    }
    _save_state(state)

    def step(label, cmd, cwd=None, timeout=900):
        state["current_step"] = label
        _save_state(state)
        result = _run(cmd, cwd=cwd, timeout=timeout)
        result["label"] = label
        state["steps"].append(result)
        _save_state(state)
        return result["rc"] == 0

    ok = True

    # Guarda quaisquer mudanças locais (uncommitted) antes do pull,
    # para não perder edições do operador feitas directamente no host.
    state["current_step"] = "git stash (mudanças locais)"
    _save_state(state)
    stash_check = _run("git status --porcelain")
    has_local = bool((stash_check.get("stdout") or "").strip())
    if has_local:
        stash = _run(
            "git stash push -u -m \"updater-autostash-$(date +%s)\""
        )
        stash["label"] = "git stash (preserva mudanças locais)"
        state["steps"].append(stash)
        _save_state(state)

    ok = ok and step(
        "git fetch", f"git fetch origin {BRANCH}",
    )
    if ok:
        ok = step(
            "git reset", f"git reset --hard origin/{BRANCH}",
        )
    if ok:
        ok = step(
            "docker compose build web",
            f"docker compose -p {PROJECT} -f {COMPOSE_FILE} build web",
            cwd=os.path.dirname(COMPOSE_FILE), timeout=900,
        )
    if ok:
        ok = step(
            "docker compose up -d (web + celery)",
            (
                f"docker compose -p {PROJECT} -f {COMPOSE_FILE} "
                "up -d --no-deps --force-recreate web celery_worker celery_beat"
            ),
            cwd=os.path.dirname(COMPOSE_FILE), timeout=300,
        )

    state["phase"] = "success" if ok else "failed"
    state["finished_at"] = time.time()
    state["current_step"] = None
    _save_state(state)


class Handler(BaseHTTPRequestHandler):
    def _check_auth(self):
        return SECRET and self.headers.get("X-Updater-Secret", "") == SECRET

    def _send_json(self, code, body):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return
        if self.path == "/status":
            if not self._check_auth():
                self._send_json(401, {"error": "unauthorized"})
                return
            self._send_json(200, _load_state())
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/update":
            return self._handle_update()
        if self.path == "/changelog-push":
            return self._handle_changelog_push()
        self.send_response(404)
        self.end_headers()

    def _handle_update(self):
        if not self._check_auth():
            self._send_json(401, {"error": "unauthorized"})
            return
        current = _load_state()
        if current.get("phase") == "running":
            self._send_json(409, {
                "error": "already running",
                "job_id": current.get("job_id"),
            })
            return
        job_id = uuid.uuid4().hex[:12]
        t = threading.Thread(
            target=_update_pipeline, args=(job_id,), daemon=True,
        )
        t.start()
        self._send_json(202, {"success": True, "job_id": job_id})

    def _handle_changelog_push(self):
        if not self._check_auth():
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode())
        except (ValueError, json.JSONDecodeError) as e:
            self._send_json(400, {"error": f"body inválido: {e}"})
            return
        content = body.get("content", "")
        token = body.get("token", "")
        repo_url = body.get("repo_url", "")
        branch = body.get("branch", BRANCH)
        commit_msg = body.get("commit_message", "chore: update changelog")
        if not content or not repo_url:
            self._send_json(400, {"error": "content e repo_url obrigatórios."})
            return

        results = []

        def run(label, cmd, cwd=None, env=None):
            r = _run(cmd, cwd=cwd or REPO, timeout=120)
            r["label"] = label
            results.append(r)
            return r["rc"] == 0

        # 1. Escrever CHANGELOG.md
        try:
            with open(os.path.join(REPO, "CHANGELOG.md"), "w") as f:
                f.write(content)
            results.append({
                "label": "Escrever CHANGELOG.md", "rc": 0,
                "stdout": f"{len(content)} bytes",
            })
        except OSError as e:
            self._send_json(500, {
                "success": False,
                "error": f"Falha a escrever CHANGELOG.md: {e}",
                "steps": results,
            })
            return

        # 2. git config (necessário para commit)
        run("git config user.name", "git config user.name 'Léguas Bot'")
        run(
            "git config user.email",
            "git config user.email 'bot@leguasfranzinas.pt'",
        )

        # 3. git add
        if not run("git add CHANGELOG.md", "git add CHANGELOG.md"):
            self._send_json(500, {
                "success": False, "error": "git add falhou", "steps": results,
            })
            return

        # 4. git commit (pode falhar se nada mudou — não é fatal)
        run(
            "git commit",
            f'git commit -m "{commit_msg}" --only CHANGELOG.md '
            f'|| echo "(sem alterações para commit)"',
        )

        # 5. Configurar remote com token e push
        if token:
            # URL com token: https://x-access-token:TOKEN@github.com/owner/repo.git
            from urllib.parse import urlparse
            p = urlparse(repo_url)
            authed_url = (
                f"{p.scheme}://x-access-token:{token}@{p.netloc}{p.path}"
            )
            if not authed_url.endswith(".git"):
                authed_url += ".git"
        else:
            authed_url = repo_url

        # Push usando URL temporária (não persiste o token na config)
        push = _run(
            f"git push '{authed_url}' HEAD:{branch}", cwd=REPO, timeout=60,
        )
        push["label"] = "git push"
        # Sanitizar token nos logs
        if token:
            push["stdout"] = (push.get("stdout") or "").replace(token, "***")
            push["stderr"] = (push.get("stderr") or "").replace(token, "***")
        results.append(push)
        if push["rc"] != 0:
            self._send_json(500, {
                "success": False,
                "error": "git push falhou",
                "steps": results,
            })
            return

        # 6. Obter o SHA do commit que foi pushado
        sha = _run("git rev-parse HEAD", cwd=REPO)
        commit_sha = (sha.get("stdout") or "").strip()

        self._send_json(200, {
            "success": True,
            "commit_sha": commit_sha,
            "steps": results,
        })

    def log_message(self, fmt, *args):
        # Logs apenas para stderr; suprimir verbosidade default
        return


def main():
    if not SECRET:
        print("ERRO: UPDATER_SECRET não definido. Defina no .env.")
        # Mesmo assim sobe — qualquer chamada vai responder 401
    print(
        f"Updater listening on :9999 (project={PROJECT}, "
        f"branch={BRANCH}, compose={COMPOSE_FILE})",
        flush=True,
    )
    httpd = ThreadingHTTPServer(("0.0.0.0", 9999), Handler)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
