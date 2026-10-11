"""Loopback only; fixed operations, per-launch token and exact Origin/Host."""
import hmac,json,secrets,webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .app import PAYLOADS
from .rea import check_prerequisites
from .store import identifier

MAX_BODY=1024*1024
ASSETS={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/validation.js':'validation.js','/style.css':'style.css',
        '/favicon.svg':'favicon.svg','/guide-debugging.svg':'guide-debugging.svg','/guide-connect.png':'guide-connect.png','/guide-review.png':'guide-review.png','/guide-restore.png':'guide-restore.png'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,status,value,content_type='application/json'):
        body=json.dumps(value,ensure_ascii=False).encode() if content_type=='application/json' else value
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def allowed(self):
        host=self.server.local_host
        if self.headers.get_all('Host')!=[host]:self.respond(403,{'error':'Invalid local Host.'});return False
        origins=self.headers.get_all('Origin')
        if origins is not None and origins!=['http://'+host]:self.respond(403,{'error':'Foreign Origin is not permitted.'});return False
        if self.path.startswith('/api/'):
            tokens=self.headers.get_all('X-Session-Token')
            if not tokens or len(tokens)!=1 or not hmac.compare_digest(tokens[0],self.server.session_token):self.respond(403,{'error':'Open the launch URL to authorize this session.'});return False
        return True
    def do_GET(self):
        if not self.allowed():return
        app=self.server.app
        try:
            if self.path in ASSETS:
                asset=ASSETS[self.path];types={'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8','svg':'image/svg+xml','png':'image/png'}
                self.respond(200,(Path(__file__).parent/'web'/asset).read_bytes(),types[asset.split('.')[-1]]);return
            if self.path=='/api/status':value={'data_dir':str(app.store.root),'scope':'Android user 0','version':'0.1.0'}
            elif self.path=='/api/dependencies':value=check_prerequisites(app.adb,app.rea)
            elif self.path=='/api/devices':value=app.adb.devices()
            elif self.path in ('/api/sessions','/api/plans'):value=app.store.list(self.path.split('/')[-1])
            elif self.path.startswith(('/api/sessions/','/api/plans/','/api/jobs/')):
                parts=self.path.split('/')
                if len(parts)!=4:raise ValueError('Invalid record path.')
                identifier(parts[3]);value=app.status(parts[3]) if parts[2]=='jobs' else app.store.load(parts[2],parts[3])
            else:self.respond(404,{'error':'Route not found.'});return
            self.respond(200,value)
        except (ValueError,TypeError) as e:self.respond(400,{'error':str(e)})
        except (FileNotFoundError,KeyError):self.respond(404,{'error':'Record or asset not found.'})
        except RuntimeError as e:self.respond(409,{'error':str(e)})
    def do_POST(self):
        if not self.allowed():return
        if not self.path.startswith('/api/'):self.respond(404,{'error':'Route not found.'});return
        try:
            if self.headers.get('Transfer-Encoding'):raise ValueError('Transfer encoding is unsupported.')
            sizes=self.headers.get_all('Content-Length')
            if not sizes or len(sizes)!=1:raise ValueError('Content-Length is required.')
            size=int(sizes[0])
            if size<0:raise ValueError('Invalid content length.')
            if size>MAX_BODY:self.close_connection=True;self.respond(413,{'error':'Request exceeds 1 MiB.'});return
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON content type is required.')
            payload=json.loads(self.rfile.read(size))
            if not isinstance(payload,dict):raise ValueError('Expected a JSON object.')
            parts=self.path.split('/')
            if len(parts)==5 and parts[2]=='jobs' and parts[4]=='cancel':
                if payload:raise ValueError('Cancellation takes no payload.')
                self.server.app.cancel(parts[3]);self.respond(200,{'message':'Cancellation requested.'});return
            if len(parts)!=3 or parts[2] not in PAYLOADS:self.respond(404,{'error':'Unknown operation.'});return
            ident=self.server.app.start(parts[2],payload);self.respond(202,{'id':ident})
        except (ValueError,TypeError,UnicodeError) as e:self.respond(400,{'error':str(e)})
        except (FileNotFoundError,KeyError):self.respond(404,{'error':'Record not found.'})
        except RuntimeError as e:self.respond(409,{'error':str(e)})
    def unsupported(self):self.respond(405,{'error':'Method is not allowed.'})
    do_PUT=do_DELETE=do_PATCH=do_OPTIONS=do_HEAD=unsupported

def create_server(app,port=0):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
    server.app=app;server.session_token=secrets.token_urlsafe(32);server.local_host='127.0.0.1:'+str(server.server_address[1])
    server.launch_url='http://'+server.local_host+'/#'+server.session_token
    return server

def serve(app,*,open_browser=True,port=0):
    server=create_server(app,port)
    print('Local browser: '+server.launch_url,flush=True)
    if open_browser:webbrowser.open(server.launch_url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
