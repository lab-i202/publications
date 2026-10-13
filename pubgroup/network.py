"""HTTPS requests with system curl, a disk cache and bounded retries.

curl uses system trust on macOS. TLS verification is never disabled.
"""
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from . import __version__

class FetchError(RuntimeError):
    pass

class Client:
    def __init__(self, directory, config, offline=False, refresh=False):
        self.directory = Path(directory); self.directory.mkdir(parents=True, exist_ok=True)
        self.config, self.offline, self.refresh = config, offline, refresh
        self.last = 0; self.robots = {}
        self.user_agent = 'PublicationGroup/' + __version__
        if config.get('contact_email'):
            self.user_agent += ' (mailto:' + config['contact_email'] + ')'
    def get(self, url, accept='text/html', headers=None):
        if urlsplit(url).scheme != 'https':
            raise FetchError('Only HTTPS collection URLs are supported')
        key = hashlib.sha256((url + '\n' + accept).encode()).hexdigest()
        body, meta = self.directory / (key + '.body'), self.directory / (key + '.json')
        if body.exists() and meta.exists():
            info = json.loads(meta.read_text())
            fresh = time.time() - info['timestamp'] < float(self.config.get('cache_hours', 24)) * 3600
            if self.offline or (fresh and not self.refresh):
                return body.read_text(encoding='utf-8'), dict(info, cached=True)
        if self.offline:
            raise FetchError('No cached response for ' + url)
        timeout = int(self.config.get('timeout_seconds', 30))
        for attempt in range(int(self.config.get('retries', 2)) + 1):
            delay = float(self.config.get('delay_seconds', .35)) - (time.monotonic() - self.last)
            if delay > 0:
                time.sleep(delay)
            with tempfile.TemporaryDirectory(prefix='pubgroup-http-') as tmp:
                target, response_headers = Path(tmp) / 'body', Path(tmp) / 'headers'
                try:
                    extra = []
                    header_input = None
                    if headers:
                        if any('\n' in str(v) or '\r' in str(v) for v in headers.values()):
                            raise FetchError('Invalid request header')
                        extra = ['--header', '@-']
                        header_input = ''.join(k + ': ' + str(v) + '\n' for k, v in headers.items())
                    r = subprocess.run(['curl', '-sS', '-L', '--proto', '=https', '--proto-redir', '=https',
                                        '--max-time', str(timeout), '--max-redirs', '4', '--user-agent', self.user_agent,
                                        '-H', 'Accept: ' + accept, '-D', str(response_headers), '-o', str(target),
                                        '-w', '%{http_code}', *extra, url], input=header_input, capture_output=True, text=True,
                                       timeout=timeout + 5)
                except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                    raise FetchError('curl missing or timed out: ' + str(exc)) from exc
                self.last = time.monotonic()
                status = int(r.stdout[-3:]) if r.stdout[-3:].isdigit() else 0
                if r.returncode == 0 and status == 200:
                    value = target.read_text(encoding='utf-8', errors='replace')
                    info = dict(url=url, timestamp=time.time(), http_status=status, cached=False)
                    body.write_text(value, encoding='utf-8'); meta.write_text(json.dumps(info))
                    return value, info
                if status in (401, 403, 404):
                    raise FetchError(f'HTTP {status}: {url}')
                if attempt == int(self.config.get('retries', 2)):
                    raise FetchError(f'HTTP {status}; curl {r.returncode}: {r.stderr[:200].strip()}')
                # Honor Retry-After (seconds), capped to keep a run bounded.
                retry_after = 0
                if response_headers.exists():
                    for line in response_headers.read_text().splitlines():
                        if line.lower().startswith('retry-after:'):
                            try:
                                retry_after = min(60, float(line.split(':', 1)[1].strip()))
                            except ValueError:
                                pass
                time.sleep(max(retry_after, min(8, 2 ** attempt)))
        raise FetchError('Request failed')
    def allowed(self, url):
        origin = 'https://' + urlsplit(url).netloc
        if origin not in self.robots:
            try:
                text, _ = self.get(origin + '/robots.txt', 'text/plain')
                robot = RobotFileParser(); robot.parse(text.splitlines())
                self.robots[origin] = robot
            except FetchError as exc:
                # A missing robots file permits normal public requests. An inaccessible
                # one does not provide permission to bypass a block.
                if 'HTTP 404' in str(exc):
                    self.robots[origin] = None
                else:
                    raise FetchError('Could not check robots.txt: ' + str(exc)) from exc
        robot = self.robots[origin]
        if robot and not robot.can_fetch(self.user_agent, url):
            raise FetchError('robots.txt disallows collection: ' + url)
        if robot:
            delay = robot.crawl_delay(self.user_agent) or robot.crawl_delay('*')
            if delay:
                self.config['delay_seconds'] = max(float(self.config.get('delay_seconds', .35)), delay)
    def json(self, url, headers=None):
        value, _ = self.get(url, 'application/json', headers=headers)
        return json.loads(value)
