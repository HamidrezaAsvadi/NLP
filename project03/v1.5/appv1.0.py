import sys
import os
import json
import pathlib
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

PROJECT_DIR = pathlib.Path(__file__).parent.resolve()
DATA_DIR = PROJECT_DIR / "Data"
OUTPUT_FILE = PROJECT_DIR / "orders_output.json"
FEEDBACK_FILE = PROJECT_DIR / "rl_feedback.json"

# Import the RLMatcher details dynamically from def2 to prevent startup failure
try:
    sys.path.append(str(PROJECT_DIR))
    from def2 import RLMatcher, RL_FEEDBACK, DEFAULT_WEIGHTS
    IMPORT_SUCCESS = True
except ImportError as e:
    # Fallback import from def3 if def2 has issues
    try:
        from def3 import RLMatcher, RL_FEEDBACK, DEFAULT_WEIGHTS
        IMPORT_SUCCESS = True
    except ImportError as e2:
        IMPORT_SUCCESS = False
        print(f"[WARN] Failed to import from def2.py or def3.py: {e} | {e2}")

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class DashboardHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress standard logging to keep the console clean
        pass

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # 1. GET / -> serve templates/index.html
        if path == '/' or path == '/index.html':
            self.serve_filepath(PROJECT_DIR / "templates" / "index.html", "text/html")
            return
            
        # 2. GET /static/... -> serve static files
        if path.startswith('/static/'):
            filename = path[8:]
            if '..' in filename or filename.startswith('/'):
                self.send_error(403, "Access Denied")
                return
            ext = os.path.splitext(filename)[1].lower()
            mime = "text/plain"
            if ext == ".css": mime = "text/css"
            elif ext == ".js": mime = "application/javascript"
            elif ext == ".png": mime = "image/png"
            elif ext in [".jpg", ".jpeg"]: mime = "image/jpeg"
            self.serve_filepath(PROJECT_DIR / "static" / filename, mime)
            return

        # 3. GET /api/orders
        if path == '/api/orders':
            if OUTPUT_FILE.exists():
                try:
                    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.send_json(data)
                except Exception as e:
                    self.send_json({"error": f"Failed to load orders: {str(e)}"}, status=500)
            else:
                self.send_json([])
            return

        # 4. GET /api/rl-summary
        if path == '/api/rl-summary':
            if not IMPORT_SUCCESS:
                self.send_json({"error": "Failed to import RL module from pipeline scripts."}, status=500)
                return
            try:
                rl = RLMatcher(FEEDBACK_FILE, DEFAULT_WEIGHTS)
                self.send_json({
                    "q_table": rl.q_table,
                    "weights": rl.weights,
                    "n_updates": rl.n_updates,
                    "summary": rl.summary()
                })
            except Exception as e:
                self.send_json({"error": f"Failed to load RL state: {str(e)}"}, status=500)
            return

        # 5. GET /api/order-file/<filename>
        if path.startswith('/api/order-file/'):
            filename = path[16:]
            if '..' in filename or filename.startswith('/'):
                self.send_error(403, "Access Denied")
                return
            filepath = DATA_DIR / filename
            if not filepath.exists():
                self.send_error(404, "File Not Found")
                return
            ext = os.path.splitext(filename)[1].lower()
            mime = "application/octet-stream"
            if ext in [".jpg", ".jpeg"]: mime = "image/jpeg"
            elif ext == ".png": mime = "image/png"
            elif ext == ".txt": mime = "text/plain; charset=utf-8"
            elif ext in [".mp3", ".wav", ".m4a"]: mime = f"audio/{ext[1:] if ext != '.m4a' else 'mp4'}"
            self.serve_filepath(filepath, mime)
            return

        # 6. GET /api/run -> Event stream (SSE)
        if path == '/api/run':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            python_exe = sys.executable
            script_name = "def3.py" if (PROJECT_DIR / "def3.py").exists() else "def2.py"
                
            proc = subprocess.Popen(
                [python_exe, script_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(PROJECT_DIR)
            )
            
            try:
                for line in proc.stdout:
                    # SSE format: data: <content>\n\n
                    msg = f"data: {line.rstrip()}\n\n"
                    self.wfile.write(msg.encode('utf-8'))
                    self.wfile.flush()
                proc.wait()
                self.wfile.write(b"data: [PROCESS_COMPLETED]\n\n")
                self.wfile.flush()
            except Exception as e:
                print(f"Error streaming logs: {e}")
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # POST /api/feedback
        if path == '/api/feedback':
            if not IMPORT_SUCCESS:
                self.send_json({"error": "Failed to import RL module from pipeline scripts."}, status=500)
                return
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                req_data = json.loads(post_data.decode('utf-8'))
            except Exception:
                self.send_json({"error": "Invalid JSON"}, status=400)
                return

            confidence = req_data.get('confidence')
            accepted = req_data.get('accepted')
            comment = req_data.get('comment', '')

            if confidence is None or accepted is None:
                self.send_json({"error": "Missing confidence or accepted status"}, status=400)
                return

            try:
                rl = RLMatcher(FEEDBACK_FILE, DEFAULT_WEIGHTS)
                if accepted:
                    rl.accept_feedback(float(confidence))
                else:
                    rl.reject_feedback(float(confidence))

                if comment:
                    print(f"[RL Comment] Decision: {'Accept' if accepted else 'Reject'} | Conf: {confidence} | Comment: {comment}")
                    log_path = PROJECT_DIR / "feedback_comments.log"
                    try:
                        with open(log_path, "a", encoding="utf-8") as lf:
                            lf.write(f"Confidence: {confidence} | Decision: {'Accepted' if accepted else 'Rejected'} | Comment: {comment}\n")
                    except Exception as le:
                        print(f"[WARN] Failed to write comment to log: {le}")

                self.send_json({
                    "status": "success",
                    "weights": rl.weights,
                    "n_updates": rl.n_updates,
                    "summary": rl.summary()
                })
            except Exception as e:
                self.send_json({"error": f"Failed to apply feedback: {str(e)}"}, status=500)
            return

        self.send_error(404, "Not Found")

    def serve_filepath(self, filepath, mime_type):
        if not filepath.exists():
            self.send_error(404, "File Not Found")
            return
        try:
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(filepath.stat().st_size))
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        except Exception as e:
            print(f"Error serving file {filepath.name}: {e}")

    def send_json(self, data, status=200):
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        except Exception as e:
            print(f"Error sending json response: {e}")

if __name__ == '__main__':
    port = 8080
    server_address = ('127.0.0.1', port)
    httpd = ThreadingHTTPServer(server_address, DashboardHandler)
    print("*" * 50)
    print(" NLP Pipeline Web Dashboard Backend Starting")
    print(f" Open http://localhost:{port} in your browser")
    print("*" * 50)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer shutting down.")
        httpd.server_close()
