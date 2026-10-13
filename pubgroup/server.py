"""Loopback-only server with token, Origin/Host checks and a single job lock.

Only web/ is served, never source, raw CVs, state, config or local output folders.
"""
import functools
import json
import secrets
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .workflow import load_config, run

def serve(config_path, port=8765):
    cfg, root = load_config(config_path)
    config_path = str(Path(config_path).resolve())
    folder = root / cfg['output'].get('web_directory', 'web')
    token, lock = secrets.token_urlsafe(32), threading.Lock()
    state = {'running': False, 'error': None}
    state_lock = threading.Lock()
    hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
    origins = {'http://' + h for h in hosts}
    class Handler(SimpleHTTPRequestHandler):
        def valid_host(self):
            return self.headers.get('Host') in hosts
        def end_headers(self):
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()
        def send_json(self, value, status=200):
            data = json.dumps(value).encode(); self.send_response(status)
            self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            if not self.valid_host():
                self.send_error(403); return
            path = urlsplit(self.path).path
            if path == '/api/status':
                if self.headers.get('Origin') and self.headers['Origin'] not in origins:
                    self.send_error(403); return
                with state_lock:
                    self.send_json(dict(state, token=token)); return
            if path.endswith('/') and path != '/':
                self.send_error(404); return
            # Deny arbitrary files even if a user accidentally copies state into web/.
            allowed = {'/', '/index.html', '/app.js', '/styles.css', '/manifest.json',
                       '/publications.json', '/publications.bib', '/report.pdf', '/bundle.enc.json', '/refresh-config.json'}
            if path not in allowed:
                self.send_error(404); return
            super().do_GET()
        def do_POST(self):
            if (not self.valid_host() or self.headers.get('Origin') not in origins
                    or self.headers.get('X-PubGroup-Token') != token):
                self.send_error(403); return
            if urlsplit(self.path).path != '/api/run':
                self.send_error(404); return
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                self.send_error(400); return
            try:
                body = json.loads(self.rfile.read(length))
                if body.get('mode') not in ('run', 'report'):
                    raise ValueError('Unknown job mode')
                period = body.get('period')
                if period is not None and period not in ('current', 'all', 'range') and not (isinstance(period, str) and period.isdigit() and len(period)==4):
                    raise ValueError('Invalid period')
                manifest = json.loads((folder / 'manifest.json').read_text())
                if manifest.get('encrypted'):
                    self.send_json({'error':'Use CLI --encrypt to preserve encrypted export'}, 409); return
            except (ValueError, OSError) as exc:
                self.send_json({'error':str(exc)}, 400); return
            if not lock.acquire(blocking=False):
                self.send_json({'error':'A job is already running'}, 409); return
            with state_lock:
                state.update(running=True, error=None)
            def worker():
                try:
                    run(config_path, period=period, refresh=body['mode']=='run', report_only=body['mode']=='report')
                except Exception as exc:
                    with state_lock:
                        state['error'] = str(exc)
                finally:
                    with state_lock:
                        state['running'] = False
                    lock.release()
            threading.Thread(target=worker, daemon=True).start()
            self.send_json({'started':True}, 202)
    handler = functools.partial(Handler, directory=str(folder))
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    print(f'Publication Group: http://127.0.0.1:{port}', flush=True)
    print('Local refresh is available in this browser. Press Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
