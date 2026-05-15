"""
Mock CleanStat Server - For testing the autonomous agent
Simulates the CleanStat backend API
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path


class MockCleanStatHandler(BaseHTTPRequestHandler):
    """Mock handler for CleanStat API"""
    
    observations = []
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/health":
            self._send_json({"status": "healthy"}, 200)
        elif self.path == "/observations":
            self._send_json({"observations": self.observations}, 200)
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == "/observations":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                observation = json.loads(post_data)
                observation["status"] = "created"
                observation["api_response"] = "mock"
                self.observations.append(observation)
                
                print(f"[MOCK SERVER] Received observation: {observation.get('id')}")
                self._send_json(observation, 201)
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, 400)
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def _send_json(self, data, status_code):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def run_mock_server(port=8000):
    """Run the mock CleanStat server"""
    server = HTTPServer(('localhost', port), MockCleanStatHandler)
    print(f"[MOCK SERVER] Starting on http://localhost:{port}")
    print(f"[MOCK SERVER] Endpoints:")
    print(f"  GET  /health        - Health check")
    print(f"  GET  /observations  - List all observations")
    print(f"  POST /observations  - Create observation")
    print(f"\n[MOCK SERVER] Press Ctrl+C to stop\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[MOCK SERVER] Shutting down")
        server.shutdown()


if __name__ == "__main__":
    run_mock_server()
