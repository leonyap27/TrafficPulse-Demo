"""Open the local usage dashboard in a browser.

Starts a tiny stdlib HTTP server rooted at the repo, finds a free port
(starting from 8765), opens the default browser at the viewer URL, and
serves until Ctrl-C.

In addition to static repo files, two virtual endpoints are exposed so the
viewer can read events without depending on a tracked manifest:

    GET /_usage/team-events.jsonl  -> concatenation of every per-user team
                                      file under `.claude/usage/team/`
    GET /_usage/live-events.jsonl  -> the current developer's live JSONL
                                      from `~/.claude-usage/<owner>/<repo>/`

Both endpoints emit `application/json-lines`. Empty responses (HTTP 200,
no body) mean "no data yet" — the viewer treats that as a normal state.

FP-192 (server); FP-196 (two-zone read path).
"""

from __future__ import annotations

import argparse
import http.server
import socket
import socketserver
import sys
import webbrowser
from pathlib import Path

# Allow importing sibling scripts so we can reuse the live-zone resolver.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import record_usage  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
VIEWER_PATH = ".claude/usage/viewer/"
TEAM_DIR = REPO_ROOT / ".claude" / "usage" / "team"
DEFAULT_PORT = 8765
PORT_SEARCH_LIMIT = 20


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _pick_port(preferred: int) -> int:
    for offset in range(PORT_SEARCH_LIMIT):
        candidate = preferred + offset
        if _port_is_free(candidate):
            return candidate
    raise RuntimeError(
        f"no free port in range {preferred}-{preferred + PORT_SEARCH_LIMIT - 1}"
    )


def _read_team_events(team_dir: Path) -> bytes:
    """Concatenate every `events-*.jsonl` under team_dir, in stable order."""
    if not team_dir.is_dir():
        return b""
    chunks: list[bytes] = []
    for path in sorted(team_dir.glob("events-*.jsonl")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if not data:
            continue
        chunks.append(data)
        if not data.endswith(b"\n"):
            chunks.append(b"\n")
    return b"".join(chunks)


def _read_live_events(live_path: Path) -> bytes:
    """Return the current developer's live JSONL bytes (empty if absent)."""
    if not live_path.is_file():
        return b""
    return live_path.read_bytes()


def _read_profile() -> bytes:
    """Return the developer profile JSON from ~/.claude-usage/profile.json."""
    profile = Path.home() / ".claude-usage" / "profile.json"
    if profile.is_file():
        return profile.read_bytes()
    return b"{}"


class _RepoHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler pinned to the repo root, quiet logs.

    Two virtual paths (`/_usage/team-events.jsonl`, `/_usage/live-events.jsonl`)
    are handled in-process; everything else falls through to the static
    file server.
    """

    _VIRTUAL = {
        "/_usage/team-events.jsonl": ("team", "application/json-lines"),
        "/_usage/live-events.jsonl": ("live", "application/json-lines"),
        "/_usage/profile.json":      ("profile", "application/json"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        virtual = self._VIRTUAL.get(self.path)
        if virtual is None:
            return super().do_GET()
        kind, content_type = virtual
        if kind == "team":
            body = _read_team_events(TEAM_DIR)
        elif kind == "live":
            body = _read_live_events(record_usage.live_events_path())
        elif kind == "profile":
            body = _read_profile()
        else:
            body = b""
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, format, *args):
        # 4xx is noise from sibling tabs polling missing endpoints; drop.
        status = args[1] if len(args) >= 2 else ""
        if isinstance(status, str) and status.startswith("4"):
            return
        line = f"  {self.address_string()} {format % args}\n"
        stream = sys.stderr if isinstance(status, str) and status.startswith("5") else sys.stdout
        stream.write(line)
        stream.flush()

    def log_error(self, format, *args):
        return


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve and open the FP-192 dashboard.")
    parser.add_argument("--port", type=int, default=None, help=f"Port (default: first free starting at {DEFAULT_PORT})")
    parser.add_argument("--no-open", action="store_true", help="Serve only; don't launch a browser")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        port = args.port if args.port is not None else _pick_port(DEFAULT_PORT)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    url = f"http://localhost:{port}/{VIEWER_PATH}"
    server = socketserver.TCPServer(("127.0.0.1", port), _RepoHandler)
    server.allow_reuse_address = True

    print(f"Serving repo root at http://localhost:{port}/")
    print(f"Dashboard: {url}")
    print("Press Ctrl-C to stop.")
    if not args.no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
