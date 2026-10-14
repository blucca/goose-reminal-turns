#!/usr/bin/env python3
"""Exercise real Goose completion hooks and Reminal state in an isolated HOME."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--goose', required=True, type=Path)
    parser.add_argument('--reminal', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path, help='New, disposable work directory')
    args = parser.parse_args()
    goose, reminal, work = (p.resolve() for p in (args.goose, args.reminal, args.work))
    work.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parent
    requests = []

    class Fixture(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append({'path': self.path, 'stream': body.get('stream', False)})
            answer = 'Local hook fixture completed.'
            base = {'id': 'local-hook-fixture', 'created': 1700000000, 'model': 'gpt-4o'}
            if body.get('stream'):
                chunks = [
                    {**base, 'object': 'chat.completion.chunk', 'choices': [
                        {'index': 0, 'delta': {'role': 'assistant', 'content': answer}, 'finish_reason': None}]},
                    {**base, 'object': 'chat.completion.chunk', 'choices': [
                        {'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                     'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}},
                ]
                data = (''.join('data: ' + json.dumps(c) + '\n\n' for c in chunks) + 'data: [DONE]\n\n').encode()
                content_type = 'text/event-stream'
            else:
                data = json.dumps({**base, 'object': 'chat.completion', 'choices': [
                    {'index': 0, 'message': {'role': 'assistant', 'content': answer}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}).encode()
                content_type = 'application/json'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = {}
    try:
        for enabled in (False, True):
            name = 'plugin' if enabled else 'baseline'
            root = work / name
            home = root / 'home'
            home.mkdir(parents=True)
            (root / 'tmp').mkdir()
            (root / 'bin').mkdir()
            (root / 'bin' / 'reminal').symlink_to(reminal)
            if enabled:
                plugin = home / '.agents/plugins/reminal-turns'
                (plugin / 'hooks').mkdir(parents=True)
                shutil.copy2(source / 'plugin.json', plugin / 'plugin.json')
                shutil.copy2(source / 'hooks/hooks.json', plugin / 'hooks/hooks.json')
            env = {**os.environ,
                   'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'),
                   'XDG_DATA_HOME': str(home / '.local/share'), 'XDG_CACHE_HOME': str(home / '.cache'),
                   'GOOSE_CONFIG_DIR': str(home / '.config/goose'), 'GOOSE_DISABLE_KEYRING': '1',
                   'GOOSE_MODE': 'auto', 'GOOSE_PROVIDER': 'openai', 'GOOSE_MODEL': 'gpt-4o',
                   'OPENAI_API_KEY': 'local-fixture-only',
                   'OPENAI_HOST': f'http://127.0.0.1:{server.server_port}',
                   'OPENAI_BASE_PATH': 'v1/chat/completions',
                   'OPENAI_BASE_URL': f'http://127.0.0.1:{server.server_port}/v1',
                   'REMINAL_SESSION': 'HOOK0001', 'REMINAL_RELAY': 'ws://127.0.0.1:1',
                   'REMINAL_WEB': 'http://127.0.0.1:1', 'REMINAL_OWNERS_DIR': str(home / 'etc'),
                   'PATH': str(root / 'bin') + os.pathsep + os.environ.get('PATH', ''),
                   'TMPDIR': str(root / 'tmp'), 'NO_PROXY': '127.0.0.1,localhost',
                   'no_proxy': '127.0.0.1,localhost'}
            subprocess.run([str(reminal), 'hook', 'working'], input=b'{}', env=env, cwd=root,
                           capture_output=True, timeout=10, check=True)
            state_file = home / '.reminal/hook-HOOK0001.state'
            before = json.loads(state_file.read_text())
            completed = subprocess.run(
                [str(goose), 'run', '--no-profile', '--text', 'Reply with a short greeting.'],
                env=env, cwd=root, capture_output=True, timeout=90)
            (root / 'stdout.txt').write_bytes(completed.stdout)
            (root / 'stderr.txt').write_bytes(completed.stderr)
            assert completed.returncode == 0, (name, completed.returncode, completed.stderr.decode(errors='replace')[-2000:])
            after = json.loads(state_file.read_text())
            expected = 'done' if enabled else 'working'
            assert after['state'] == expected, (name, expected, after)
            if enabled:
                assert after['ts'] != before['ts'], 'Expected a fresh completion hook write'
            conversation = home / '.reminal/restore/HOOK0001.conv'
            captured = conversation.exists() and bool(conversation.read_text().strip())
            assert captured == enabled, (name, 'Goose conversation ID capture', captured)
            results[name] = {'before': before['state'], 'after': after['state'],
                             'conversation_captured': captured}
        assert requests, 'Local response fixture received no requests'
        report = {'fixture': 'local deterministic HTTP responses; real Goose and Reminal binaries',
                  'results': results, 'local_requests': requests}
        (work / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
