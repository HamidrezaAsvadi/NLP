import sys
import site

# Dynamically inject user site-packages directory to resolve imports
user_site = site.getusersitepackages() if hasattr(site, 'getusersitepackages') else None
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

import os
import json
import pathlib
import subprocess
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)  # Enable CORS for convenience

PROJECT_DIR = pathlib.Path(__file__).parent
DATA_DIR = PROJECT_DIR / "Data"
OUTPUT_FILE = PROJECT_DIR / "orders_output.json"
FEEDBACK_FILE = PROJECT_DIR / "rl_feedback.json"

# Import the RLMatcher details from def2 dynamically to prevent startup failure
try:
    sys.path.append(str(PROJECT_DIR))
    from def2 import RLMatcher, RL_FEEDBACK, DEFAULT_WEIGHTS
    IMPORT_SUCCESS = True
except ImportError as e:
    IMPORT_SUCCESS = False
    print(f"[WARN] Failed to import from def2.py: {e}")

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/api/orders')
def get_orders():
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": f"Failed to load orders: {str(e)}"}), 500
    return jsonify([])

@app.route('/api/rl-summary')
def get_rl_summary():
    if not IMPORT_SUCCESS:
        return jsonify({"error": "Failed to import RL module from def2.py. Ensure def2.py is syntax-valid."}), 500
    
    try:
        rl = RLMatcher(FEEDBACK_FILE, DEFAULT_WEIGHTS)
        return jsonify({
            "q_table": rl.q_table,
            "weights": rl.weights,
            "n_updates": rl.n_updates,
            "summary": rl.summary()
        })
    except Exception as e:
        return jsonify({"error": f"Failed to load RL state: {str(e)}"}), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    if not IMPORT_SUCCESS:
        return jsonify({"error": "Failed to import RL module from def2.py. Ensure def2.py is syntax-valid."}), 500
    
    req_data = request.json or {}
    confidence = req_data.get('confidence')
    accepted = req_data.get('accepted')
    
    if confidence is None or accepted is None:
        return jsonify({"error": "Missing confidence or accepted status"}), 400
    
    try:
        rl = RLMatcher(FEEDBACK_FILE, DEFAULT_WEIGHTS)
        if accepted:
            rl.accept_feedback(float(confidence))
        else:
            rl.reject_feedback(float(confidence))
            
        return jsonify({
            "status": "success",
            "weights": rl.weights,
            "n_updates": rl.n_updates,
            "summary": rl.summary()
        })
    except Exception as e:
        return jsonify({"error": f"Failed to apply feedback: {str(e)}"}), 500

@app.route('/api/run')
def run_pipeline():
    def generate():
        python_exe = sys.executable
        # Run def2.py in a subprocess, streaming output
        proc = subprocess.Popen(
            [python_exe, 'def2.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(PROJECT_DIR)
        )
        
        for line in proc.stdout:
            yield f"data: {line}\n\n"
            
        proc.wait()
        yield "data: [PROCESS_COMPLETED]\n\n"
        
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/order-file/<path:filename>')
def get_order_file(filename):
    try:
        # Secure routing to serve files only from the Data directory
        return send_from_directory(DATA_DIR, filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 404

if __name__ == '__main__':
    # Listen on localhost:5000
    print("*" * 50)
    print(" NLP Pipeline Web Dashboard Backend Starting")
    print(" Open http://localhost:8080 in your browser")
    print("*" * 50)
    app.run(host='127.0.0.1', port=8080, debug=True)
