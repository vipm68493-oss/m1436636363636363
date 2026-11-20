import os
import sys
import subprocess
import glob
import threading
import time
from flask import Flask, render_template_string, request, redirect, url_for, jsonify

app = Flask(__name__)

UPLOAD_FOLDER = "uploaded"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

bot_process = None
log_buffer = []
current_file = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Python Runner Control Panel</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: #e2e8f0; padding: 20px;
            display: flex; justify-content: center; align-items: flex-start;
            min-height: 100vh;
        }
        .container {
            width: 100%; max-width: 960px; background: #1e293b;
            border-radius: 18px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.6);
            overflow: hidden; border: 1px solid #334155;
        }
        .header { background: linear-gradient(90deg,#2563eb,#7c3aed); padding:24px; text-align:center; }
        .header h1 { font-size: 26px; font-weight: 700; }
        .header p { font-size: 13px; opacity: 0.85; margin-top: 4px; }
        .status-bar {
            display:flex; align-items:center; justify-content:space-between;
            padding:16px 24px; background:#1e293b; border-bottom:1px solid #334155;
            flex-wrap:wrap; gap:12px;
        }
        .status-info { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
        .status-badge {
            display:inline-flex; align-items:center; gap:8px;
            padding:7px 14px; border-radius:9999px; font-size:14px; font-weight:600;
        }
        .status-running { background:#064e3b; color:#6ee7b7; border:1px solid #10b981; }
        .status-stopped { background:#7f1d1d; color:#fca5a5; border:1px solid #ef4444; }
        .dot { width:9px; height:9px; border-radius:50%; }
        .dot-green { background:#10b981; animation:pulse 1.8s infinite; }
        .dot-red { background:#ef4444; }
        @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.4;} }
        .file-tag { font-size:13px; padding:6px 12px; border-radius:8px;
            background:#334155; color:#93c5fd; font-family:monospace; }
        .section { padding:18px 24px; border-bottom:1px solid #334155; background:#0f172a; }
        .section h3 { font-size:14px; color:#94a3b8; margin-bottom:12px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; }
        .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
        .row select, .row input[type=file] {
            flex:1; min-width:200px; padding:10px 14px;
            background:#1e293b; color:#e2e8f0;
            border:1px solid #475569; border-radius:8px; font-size:14px; outline:none;
        }
        .row select:focus { border-color:#3b82f6; }
        input[type=file]::file-selector-button {
            background:#475569; color:white; border:none; padding:6px 12px;
            border-radius:6px; cursor:pointer; margin-right:8px; font-size:13px;
        }
        .controls {
            display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
            gap:12px; padding:20px 24px;
        }
        .btn {
            padding:13px 20px; border:none; border-radius:10px;
            font-size:15px; font-weight:600; cursor:pointer;
            transition:all 0.15s; display:inline-flex;
            align-items:center; justify-content:center; gap:6px; color:white;
        }
        .btn:active { transform: scale(0.97); }
        .btn-primary { background:#3b82f6; } .btn-primary:hover { background:#2563eb; }
        .btn-danger { background:#ef4444; } .btn-danger:hover { background:#dc2626; }
        .btn-warning { background:#f59e0b; color:#1e293b; } .btn-warning:hover { background:#d97706; }
        .btn-secondary { background:#475569; } .btn-secondary:hover { background:#334155; }
        .btn-success { background:#10b981; } .btn-success:hover { background:#059669; }
        .terminal { margin:0 24px 24px 24px; background:#000;
            border-radius:10px; overflow:hidden; border:1px solid #334155; }
        .terminal-header { background:#1e293b; padding:10px 18px;
            font-size:12px; color:#94a3b8; display:flex; justify-content:space-between; }
        .terminal-body { padding:16px; height:360px; overflow-y:auto;
            font-family:'Consolas','Courier New',monospace; font-size:13px;
            color:#a5f3fc; line-height:1.6; white-space:pre-wrap; word-break:break-all; }
        .terminal-body::-webkit-scrollbar { width:8px; }
        .terminal-body::-webkit-scrollbar-track { background:#0f172a; }
        .terminal-body::-webkit-scrollbar-thumb { background:#475569; border-radius:4px; }
        .log-line { margin-bottom:2px; }
        .log-error { color:#fca5a5; } .log-info { color:#6ee7b7; } .log-warn { color:#fcd34d; }
        .footer { text-align:center; padding:14px; font-size:12px;
            color:#64748b; border-top:1px solid #334155; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐍 Python Runner Control Panel</h1>
            <p>Upload a .py file or select an existing one, then run it</p>
        </div>

        <div class="status-bar">
            <div class="status-info">
                <span>Status:</span>
                <span class="status-badge {% if is_running %}status-running{% else %}status-stopped{% endif %}" id="status-badge">
                    <span class="dot {% if is_running %}dot-green{% else %}dot-red{% endif %}" id="status-dot"></span>
                    <span id="status-text">{% if is_running %}Running{% else %}Stopped{% endif %}</span>
                </span>
            </div>
            <div class="status-info">
                <span>Active file:</span>
                <span class="file-tag" id="active-file">{{ current_file or 'None' }}</span>
            </div>
        </div>

        <div class="section">
            <h3>📤 Upload Python File</h3>
            <form method="post" action="/upload" enctype="multipart/form-data" class="row">
                <input type="file" name="file" accept=".py" required>
                <button type="submit" class="btn btn-success" style="padding:10px 18px;">Upload</button>
            </form>
        </div>

        <div class="section">
            <h3>📁 Select Existing File</h3>
            <form method="post" action="/select" class="row">
                <select name="pyfile">
                    {% for f in py_files %}
                    <option value="{{ f }}" {% if f == current_file %}selected{% endif %}>{{ f }}</option>
                    {% endfor %}
                    {% if not py_files %}
                    <option value="">No .py files found</option>
                    {% endif %}
                </select>
                <button type="submit" class="btn btn-secondary" style="padding:10px 18px;">Select</button>
            </form>
        </div>

        <div class="controls">
            <form action="/start" method="post" style="display:contents;">
                <button type="submit" class="btn btn-primary">▶ Start</button>
            </form>
            <form action="/stop" method="post" style="display:contents;">
                <button type="submit" class="btn btn-danger">⏹ Stop</button>
            </form>
            <form action="/restart" method="post" style="display:contents;">
                <button type="submit" class="btn btn-warning">🔄 Restart</button>
            </form>
            <form action="/install" method="post" style="display:contents;">
                <button type="submit" class="btn btn-success">📦 Install Deps</button>
            </form>
            <form action="/clear" method="post" style="display:contents;">
                <button type="submit" class="btn btn-secondary">🧹 Clear Logs</button>
            </form>
        </div>

        <div class="terminal">
            <div class="terminal-header">
                <span>Terminal Output</span>
                <span>Live · last 300 lines</span>
            </div>
            <div class="terminal-body" id="log-box">
                {% for line in logs %}
                <div class="log-line {% if 'Error' in line or 'Traceback' in line or 'Exception' in line or 'ERROR' in line %}log-error{% elif 'WARNING' in line %}log-warn{% elif 'INFO' in line %}log-info{% endif %}">{{ line }}</div>
                {% endfor %}
                {% if not logs %}
                <div style="color:#64748b;">No logs yet. Upload or select a file and press Start.</div>
                {% endif %}
            </div>
        </div>

        <div class="footer">Running on Render · Auto-refreshes every 2s</div>
    </div>

    <script>
        setInterval(function() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    const logBox = document.getElementById('log-box');
                    if (data.logs && data.logs.length > 0) {
                        logBox.innerHTML = data.logs.map(line => {
                            let cls = 'log-line';
                            if (line.includes('Error') || line.includes('Traceback') || line.includes('Exception') || line.includes('ERROR')) cls += ' log-error';
                            else if (line.includes('WARNING')) cls += ' log-warn';
                            else if (line.includes('INFO')) cls += ' log-info';
                            return `<div class="${cls}">${line.replace(/</g,'&lt;')}</div>`;
                        }).join('');
                        logBox.scrollTop = logBox.scrollHeight;
                    } else {
                        logBox.innerHTML = '<div style="color:#64748b;">No logs yet. Upload or select a file and press Start.</div>';
                    }
                    const badge = document.getElementById('status-badge');
                    const dot = document.getElementById('status-dot');
                    const txt = document.getElementById('status-text');
                    if (data.is_running) {
                        badge.className = 'status-badge status-running';
                        dot.className = 'dot dot-green';
                        txt.textContent = 'Running';
                    } else {
                        badge.className = 'status-badge status-stopped';
                        dot.className = 'dot dot-red';
                        txt.textContent = 'Stopped';
                    }
                    document.getElementById('active-file').textContent = data.current_file || 'None';
                });
        }, 2000);
    </script>
</body>
</html>
"""

def list_py_files():
    root_files = [f for f in glob.glob("*.py") if f != "app.py"]
    uploaded = [os.path.join(UPLOAD_FOLDER, f) for f in glob.glob(os.path.join(UPLOAD_FOLDER, "*.py"))]
    return sorted(root_files + uploaded)

def read_logs():
    global log_buffer
    return log_buffer[-300:]

def is_running():
    global bot_process
    if bot_process is None:
        return False
    return bot_process.poll() is None

def start_process(filename):
    global bot_process, log_buffer, current_file
    if is_running():
        return False, "Already running"
    if not filename or not os.path.exists(filename):
        log_buffer.append(f"ERROR: File not found: {filename}")
        return False, "File not found"

    current_file = filename
    log_buffer.append(f"--- Starting {filename} ---")
    try:
        bot_process = subprocess.Popen(
            [sys.executable, "-u", filename],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=os.environ.copy(),
        )

        def read_output():
            for line in iter(bot_process.stdout.readline, ''):
                if line:
                    log_buffer.append(line.rstrip())
            bot_process.stdout.close()

        threading.Thread(target=read_output, daemon=True).start()
        log_buffer.append(f"--- {filename} started ---")
        return True, "Started"
    except Exception as e:
        log_buffer.append(f"ERROR starting: {str(e)}")
        return False, str(e)

def stop_process():
    global bot_process
    if bot_process is None or bot_process.poll() is not None:
        return False, "Not running"
    log_buffer.append("--- Stopping process ---")
    try:
        bot_process.terminate()
        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_process.kill()
        bot_process = None
        log_buffer.append("--- Process stopped ---")
        return True, "Stopped"
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    return render_template_string(
        HTML_TEMPLATE, is_running=is_running(),
        logs=read_logs(), py_files=list_py_files(),
        current_file=current_file,
    )

@app.route('/select', methods=['POST'])
def select():
    global current_file
    current_file = request.form.get('pyfile', '')
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
def upload():
    global current_file, log_buffer
    f = request.files.get('file')
    if not f or not f.filename.endswith('.py'):
        log_buffer.append("ERROR: Please upload a .py file")
        return redirect(url_for('index'))
    safe_name = os.path.basename(f.filename)
    path = os.path.join(UPLOAD_FOLDER, safe_name)
    f.save(path)
    current_file = path
    log_buffer.append(f"--- Uploaded {safe_name} ---")
    return redirect(url_for('index'))

@app.route('/start', methods=['POST'])
def start():
    global current_file
    if not current_file:
        files = list_py_files()
        if files:
            current_file = files[0]
    start_process(current_file)
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop():
    stop_process()
    return redirect(url_for('index'))

@app.route('/restart', methods=['POST'])
def restart():
    global current_file
    stop_process()
    time.sleep(1)
    start_process(current_file)
    return redirect(url_for('index'))

@app.route('/install', methods=['POST'])
def install():
    global log_buffer
    log_buffer.append("--- Installing dependencies ---")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            capture_output=True, text=True, timeout=180
        )
        for line in (result.stdout or "").splitlines():
            log_buffer.append(line)
        if result.returncode == 0:
            log_buffer.append("--- Dependencies installed successfully ---")
        else:
            for line in (result.stderr or "").splitlines():
                log_buffer.append(line)
            log_buffer.append("--- Install FAILED ---")
    except Exception as e:
        log_buffer.append(f"--- Install error: {str(e)} ---")
    return redirect(url_for('index'))

@app.route('/clear', methods=['POST'])
def clear():
    global log_buffer
    log_buffer = []
    return redirect(url_for('index'))

@app.route('/api/status')
def api_status():
    return jsonify({
        'is_running': is_running(),
        'logs': read_logs(),
        'current_file': current_file,
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)