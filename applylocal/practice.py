"""An entirely local practice page, served only on loopback."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

from .browser import resource_text

_server = None


def practice_url() -> str:
    global _server
    if _server is None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/practice":
                    self.send_error(404)
                    return
                body = resource_text("practice.html").encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass
        _server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=_server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{_server.server_port}/practice"
