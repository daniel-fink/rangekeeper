"""Serve local notebook displays without a service or browser dependency."""

import atexit
import secrets
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote, unquote, urlsplit


class LocalDisplay:
    """A loopback-only, read-only display root. Close it when its kernel is done.

    A random URL prefix limits access to this instance. Directory listings and
    paths outside the explicit root are refused, including symlink escapes.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory).resolve(strict=True)
        if not self.directory.is_dir():
            raise ValueError("Display root must be a directory")
        token = secrets.token_urlsafe(24)
        root = self.directory

        class Handler(SimpleHTTPRequestHandler):
            def do_GET(self):
                self._read(super().do_GET)

            def do_HEAD(self):
                self._read(super().do_HEAD)

            def _read(self, respond):
                path = urlsplit(self.path).path
                prefix = "/" + token + "/"
                if not path.startswith(prefix):
                    self.send_error(404)
                    return
                relative = unquote(path[len(prefix) :])
                target = (root / relative).resolve()
                if not target.is_relative_to(root) or not target.is_file():
                    self.send_error(404)
                    return
                self.path = "/" + quote(relative, safe="/")
                respond()

            def log_message(self, format, *args):
                pass

        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(Handler, directory=str(root))
        )
        self._server.daemon_threads = True
        self.base_url = f"http://127.0.0.1:{self._server.server_port}/{token}/"
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._closed = False
        atexit.register(self.close)

    def url(self, path: str | Path) -> str:
        """Return a URL for a file under this root; preserve a view query."""
        if self._closed:
            raise ValueError("Display server is closed")
        parts = urlsplit(str(path))
        if parts.scheme or parts.netloc:
            raise ValueError("Supply a local file path")
        target = (self.directory / unquote(parts.path)).resolve(strict=True)
        if not target.is_relative_to(self.directory) or not target.is_file():
            raise ValueError("Display file must be inside the display root")
        result = self.base_url + quote(target.relative_to(self.directory).as_posix())
        return result + ("?" + parts.query if parts.query else "")

    def close(self):
        if not self._closed:
            self._closed = True
            self._server.shutdown()
            self._server.server_close()
            self._thread.join()
            atexit.unregister(self.close)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
