import http.client,json,tempfile,threading,time,unittest
from pathlib import Path
from tests.support import fake_adb,fixture_catalog,change_state
from tcl_tv_debloat.app import Application
from tcl_tv_debloat.store import Store
from tcl_tv_debloat.rea import Rea
from tcl_tv_debloat.server import create_server

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name)
        adb,self.state=fake_adb(root);self.app=Application(adb,Store(root/'data'),fixture_catalog(),Rea())
        self.server=create_server(self.app);self.port=self.server.server_address[1]
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,method='GET',data=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        h={'X-Session-Token':self.server.session_token,'Content-Type':'application/json',**(headers or {})}
        c.request(method,path,body=json.dumps(data) if data is not None else None,headers=h)
        r=c.getresponse();body=r.read();status=r.status;c.close()
        try:return status,json.loads(body)
        except ValueError:return status,body
    def operation(self,name,payload):
        status,j=self.request('/api/'+name,'POST',payload);self.assertEqual(status,202,j)
        end=time.monotonic()+20
        while time.monotonic()<end:
            _,j=self.request('/api/jobs/'+j['id'])
            if j['status'] not in ('running','pending'):break
            time.sleep(.05)
        self.assertEqual(j['status'],'complete',j)
        return j
    def test_rejected_http_inputs_do_not_contact_device(self):
        cases=[('/api/devices','GET',None,{'X-Session-Token':''},403),('/api/devices','GET',None,{'Origin':'https://evil.example'},403),('/api/devices','GET',None,{'Host':'evil.example'},403),('/api/shell','POST',{'command':'id'},None,404),('/api/apply','GET',None,None,404),('/api/status','PUT',{},None,405),('/../../state.json','GET',None,None,404),('/api/sessions/../../state.json','GET',None,None,400),('/api/scan','POST',{'serial':'x'},None,400)]
        for path,method,data,headers,want in cases:self.assertEqual(self.request(path,method,data,headers)[0],want)
        self.assertFalse(self.state.with_name('commands.jsonl').exists())
        c=http.client.HTTPConnection('127.0.0.1',self.port)
        c.request('POST','/api/scan',body='',headers={'X-Session-Token':self.server.session_token,'Content-Type':'application/json','Content-Length':str(1024*1024+1)})
        r=c.getresponse();self.assertEqual(r.status,413);r.read();c.close()
    def test_authorized_scan_preview_apply_and_restore(self):
        inv=self.operation('scan',{'serial':'fixture-tv','deep':False})['result_id']
        plan=self.operation('preview',{'inventory_id':inv,'selection':{'com.example.optional':'disable'}})['result_id']
        self.operation('apply',{'plan_id':plan})
        self.assertEqual(json.loads(self.state.read_text())['packages']['com.example.optional']['enabled'],3)
        inv=self.operation('scan',{'serial':'fixture-tv','deep':False})['result_id']
        undo=self.operation('restore_preview',{'inventory_id':inv,'source_plan_id':plan})['result_id']
        self.operation('restore',{'plan_id':undo})
        self.assertEqual(json.loads(self.state.read_text())['packages']['com.example.optional']['enabled'],0)
    def test_busy_and_invalid_json(self):
        change_state(self.state,delay=.1)
        ident=self.app.start('scan',{'serial':'fixture-tv','deep':False})
        self.assertEqual(self.request('/api/scan','POST',{'serial':'fixture-tv','deep':False})[0],409)
        self.app.cancel(ident)
        while self.app.status(ident)['status']=='running':time.sleep(.05)
        c=http.client.HTTPConnection('127.0.0.1',self.port)
        c.request('POST','/api/scan',body='{bad',headers={'X-Session-Token':self.server.session_token,'Content-Type':'application/json'})
        r=c.getresponse();self.assertEqual(r.status,400);r.read();c.close()

    def test_local_walkthrough_assets_have_image_types_and_no_path_escape(self):
        # Catches broken guide images or a broad static route exposing private files.
        for asset,kind,signature in [('guide-debugging.svg','image/svg+xml',b'<svg'),('guide-review.png','image/png',b'\x89PNG'),('guide-restore.png','image/png',b'\x89PNG')]:
            c=http.client.HTTPConnection('127.0.0.1',self.port)
            c.request('GET','/'+asset)
            response=c.getresponse();body=response.read();c.close()
            self.assertEqual(response.status,200,asset)
            self.assertTrue(response.getheader('Content-Type').startswith(kind))
            self.assertTrue(body.startswith(signature))
        self.assertEqual(self.request('/guide/../../state.json')[0],404)
        self.assertFalse(self.state.with_name('commands.jsonl').exists())
