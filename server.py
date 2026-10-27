"""Web server for the Pixeline games: prepares new discs from ISO_DIR into DATA_DIR in the
background, then serves a game list, a player page per game and the game files.

Game file lookup is forgiving, because the games ask for paths in whatever case and folder
the original CD happened to use:
  1. the path lowercased (prepare.py lowercases every name)
  2. the same with .cct <-> .cxt swapped (DirPlayer asks for Shockwave .cct casts), or with
     .dxr/.dir/.dcr added to a bare movie name (`go to movie "BUSSEN\BUSSEN"`: DirPlayer adds
     no extension when the host is an IP address, mistaking its dots for one)
  3. a file with that name anywhere in the game (casts linked by bare file name)
"""
import gzip, html, json, mimetypes, os, threading, urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import prepare

APP = os.path.dirname(os.path.abspath(__file__))
PLAYER_DIR = os.environ.get('PLAYER_DIR', os.path.join(APP, 'player'))
DATA_DIR = os.environ.get('DATA_DIR', '/data')
ISO_DIR = os.environ.get('ISO_DIR', '/isos')
PORT = int(os.environ.get('PORT', '8080'))

status = {'busy': False, 'log': []}
by_name = {}          # slug -> {basename: relative path}, built lazily
gzipped = {}          # player file path -> (mtime, gzip bytes)


def log(msg):
    print(msg, flush=True)
    status['log'] = (status['log'] + [msg])[-20:]


def prepare_all():
    status['busy'] = True
    try:
        if os.path.isdir(ISO_DIR):
            for f in sorted(os.listdir(ISO_DIR)):
                p = os.path.join(ISO_DIR, f)
                if f.lower().endswith('.iso') or os.path.isdir(p):
                    try:
                        prepare.prepare(p, DATA_DIR, log)
                    except Exception as e:  # one bad disc must not stop the rest
                        log(f'{f}: fejl under klargøring: {e}')
    finally:
        status['busy'] = False
        by_name.clear()


def games():
    out = []
    for slug in sorted(os.listdir(DATA_DIR)) if os.path.isdir(DATA_DIR) else []:
        meta = os.path.join(DATA_DIR, slug, 'meta.json')
        if os.path.exists(meta):
            out.append(json.load(open(meta, encoding='utf-8')))
    return sorted(out, key=lambda g: g['title'])


def resolve_game_file(slug, rel):
    root = os.path.realpath(os.path.join(DATA_DIR, slug))
    rel = rel.lower().replace('\\', '/')
    candidates = [rel]
    stem, ext = os.path.splitext(rel)
    if ext in ('.cct', '.cxt'):
        candidates.append(stem + ('.cxt' if ext == '.cct' else '.cct'))
    elif not ext:
        candidates += [rel + e for e in ('.dxr', '.dir', '.dcr')]
    for c in candidates:
        p = os.path.realpath(os.path.join(root, c))
        if p.startswith(root + os.sep) and os.path.isfile(p):
            return p
    if slug not in by_name:
        index = {}
        for d, _, files in os.walk(root):
            for f in files:
                index.setdefault(f, os.path.join(d, f))
        by_name[slug] = index
    for c in candidates:
        p = by_name[slug].get(os.path.basename(c))
        if p:
            return p
    return None


PAGE = '''<!doctype html><html lang="da"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<link rel="manifest" href="/manifest.webmanifest">
<title>{title}</title><style>
html,body{{margin:0;height:100%;background:#000;color:#fff;font-family:system-ui,sans-serif}}
{style}</style>{head}</head><body>{body}</body></html>'''

INDEX_STYLE = '''main{max-width:640px;margin:0 auto;padding:24px 16px}
h1{font-size:28px;color:#ffd800}
a.game{display:block;padding:18px 16px;margin:10px 0;border-radius:12px;background:#c8102e;
color:#ffd800;font-size:20px;font-weight:700;text-decoration:none}
.note{color:#aaa;font-size:14px}'''

PLAYER_STYLE = '''body{overflow:hidden}
#stage{position:fixed;inset:0}
#start{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;
background:#000;color:#ffd800;font-size:28px;font-weight:700;z-index:10;cursor:pointer}
#back{position:fixed;top:8px;left:8px;z-index:5;color:#666;font-size:14px;text-decoration:none}'''

# The embed fills the screen; the (patched) player scales the stage to fit it. A tap is
# required first: iOS only allows audio after a user gesture. The 15 MB player loads with
# defer, so the page shows "Indlæser…" until it is ready instead of ignoring taps.
PLAYER_BODY = '''<a id="back" href="/">&#8592;</a><div id="stage"></div>
<div id="start">Indlæser …</div>
<script>
var start = document.getElementById('start');
document.addEventListener('DOMContentLoaded', function () {{
  start.textContent = 'Tryk for at starte';
  start.addEventListener('click', function () {{
    start.remove();
    var e = document.createElement('embed');
    e.setAttribute('src', '/games/{slug}/main.dxr');
    e.setAttribute('type', 'application/x-director');
    e.setAttribute('width', innerWidth);
    e.setAttribute('height', innerHeight);
    document.getElementById('stage').appendChild(e);
    DirPlayer.init();
  }});
}});
</script>'''


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if os.environ.get('DEBUG'):
            super().log_message(fmt, *args)

    def send_body(self, body, ctype, code=200, cache='no-cache', encoding=None):
        data = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', cache)
        if encoding:
            self.send_header('Content-Encoding', encoding)
            self.send_header('Vary', 'Accept-Encoding')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def send_file(self, path, cache, compress=False):
        ctype = {'.js': 'text/javascript', '.wasm': 'application/wasm', '.json': 'application/json',
                 '.map': 'application/json'}.get(os.path.splitext(path)[1].lower())
        ctype = ctype or mimetypes.guess_type(path)[0] or 'application/octet-stream'
        if compress and 'gzip' in self.headers.get('Accept-Encoding', ''):
            # the player bundle halves in size; compress once and keep it in memory
            mtime = os.path.getmtime(path)
            if gzipped.get(path, (None,))[0] != mtime:
                gzipped[path] = (mtime, gzip.compress(open(path, 'rb').read(), 6))
            return self.send_body(gzipped[path][1], ctype, cache=cache, encoding='gzip')
        self.send_body(open(path, 'rb').read(), ctype, cache=cache)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        parts = [p for p in path.split('/') if p]
        if not parts:
            return self.index()
        if parts == ['manifest.webmanifest']:
            return self.send_body(json.dumps({'name': 'Pixeline', 'short_name': 'Pixeline',
                'start_url': '/', 'display': 'fullscreen', 'orientation': 'landscape',
                'background_color': '#000000', 'theme_color': '#c8102e'}), 'application/manifest+json')
        if parts[0] == 'play' and len(parts) == 2:
            g = next((g for g in games() if g['slug'] == parts[1]), None)
            if not g:
                return self.send_body('Ukendt spil', 'text/plain; charset=utf-8', 404)
            return self.send_body(PAGE.format(title=html.escape(g['title']), style=PLAYER_STYLE,
                head='<script src="/player/dirplayer-polyfill.js" defer data-manual-init></script>',
                body=PLAYER_BODY.format(slug=g['slug'])), 'text/html; charset=utf-8')
        if parts[0] == 'player' and len(parts) > 1:
            root = os.path.realpath(PLAYER_DIR)
            p = os.path.realpath(os.path.join(root, *parts[1:]))
            if p.startswith(root + os.sep) and os.path.isfile(p):
                return self.send_file(p, 'public, max-age=86400', compress=True)
        if parts[0] == 'games' and len(parts) > 2:
            p = resolve_game_file(parts[1], '/'.join(parts[2:]))
            if p:
                return self.send_file(p, 'public, max-age=3600')
        self.send_body('Ikke fundet', 'text/plain; charset=utf-8', 404)

    def index(self):
        items = ''.join(f'<a class="game" href="/play/{html.escape(g["slug"])}">{html.escape(g["title"])}</a>'
                        for g in games())
        note = ''
        if status['busy']:
            note = '<p class="note">Klargør spil … genindlæs siden om lidt.</p>'
        if status['log']:
            note += '<p class="note">' + '<br>'.join(html.escape(m) for m in status['log'][-5:]) + '</p>'
        if not items and not status['busy']:
            note += f'<p class="note">Ingen spil fundet. Læg ISO-filerne i mappen der er koblet til {html.escape(ISO_DIR)}.</p>'
        self.send_body(PAGE.format(title='Pixeline', style=INDEX_STYLE, head='',
            body=f'<main><h1>Pixeline</h1>{items}{note}</main>'), 'text/html; charset=utf-8')


if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    threading.Thread(target=prepare_all, daemon=True).start()
    print(f'Pixeline kører på port {PORT}', flush=True)
    ThreadingHTTPServer(('', PORT), Handler).serve_forever()
