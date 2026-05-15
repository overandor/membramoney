from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from app.api.health_routes import health_payload
from app.api.metrics_routes import metrics_payload
from app.api.positions_routes import positions_payload
from app.api.orders_routes import orders_payload
from app.api.dashboard_routes import dashboard_payload
from app.api.unified_balance_routes import unified_balance_payload
from app.api.ui_routes import unified_ui_html

class APIServer:
    def __init__(self, host: str, port: int, state: dict) -> None:
        self.host = host
        self.port = port
        self.state = state
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, payload: dict, code: int = 200):
                raw = json.dumps(payload, default=str).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_html(self, payload: str, code: int = 200):
                raw = payload.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                return

            def do_GET(self):
                path = urlparse(self.path).path
                if path in ("/", "/ui"):
                    return self._send_html(unified_ui_html())
                if path == "/health":
                    return self._send(health_payload(outer.state["app_state"]))
                if path == "/metrics":
                    return self._send(metrics_payload(outer.state["metrics"]))
                if path == "/positions":
                    return self._send({"rows": positions_payload(outer.state["position_repo"], outer.state["symbols"])})
                if path == "/orders":
                    return self._send({"rows": orders_payload(outer.state["order_repo"])})
                if path == "/dashboard":
                    return self._send(dashboard_payload(outer.state["engine_state"]))
                if path == "/unified-balance":
                    return self._send(unified_balance_payload(outer.state["unified_balance_service"]))
                return self._send({"error": "not_found"}, 404)

        self.httpd = ThreadingHTTPServer((host, port), Handler)

    def start_in_thread(self):
        import threading
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
