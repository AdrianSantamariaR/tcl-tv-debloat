"""Optional local REA integration; configuration is not proof of execution."""
import copy,hashlib,json,os,re,shutil,signal,subprocess,tempfile,time,zipfile
from pathlib import Path
from .inventory import record

REA_DOC='https://github.com/morluto/rea/blob/main/docs/android-analysis.md'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def node_compatible(version,requirement):
    version=tuple(map(int,version.lstrip('v').split('.')[:3]));matched=False
    for branch in requirement.split('||'):
        m=re.fullmatch(r'\s*(\^|>=)(\d+)\.(\d+)\.(\d+)\s*',branch)
        if not m:raise ValueError('Unsupported Node engine range syntax.')
        minimum=tuple(map(int,m.groups()[1:]));matched |= version>=minimum and (m[1]=='>=' or version[0]==minimum[0])
    return matched

def probe(command,env):
    try:
        r=subprocess.run(command,text=True,capture_output=True,env=env,timeout=10)
        if r.returncode:raise RuntimeError('Dependency probe failed.')
        return (r.stdout or r.stderr).strip()
    except (OSError,subprocess.TimeoutExpired) as e:raise RuntimeError('Dependency is missing or timed out.') from e

class ReaError(RuntimeError):
    def __init__(self,message,observation=None):
        super().__init__(message);self.observation=observation

class ConfigurationRequired(RuntimeError):pass

class Rea:
    def __init__(self,command=None,env=None):
        self.env={**os.environ,**(env or {})};self.command=list(command) if command else None
        self.timeout=180;self.execution_verified=False
    def identity(self):
        rows=[]
        def row(name,purpose,url,fn):
            try:version,detail=fn();status='configured'
            except ConfigurationRequired as e:version=None;detail=str(e);status='needs_configuration'
            except FileNotFoundError as e:version=None;detail=str(e);status='missing'
            except (ValueError,RuntimeError,OSError,KeyError,zipfile.BadZipFile) as e:version=None;detail=str(e);status='unavailable'
            rows.append({'name':name,'purpose':purpose,'status':status,'version':version,'setup_url':url,'detail':detail,'required_for':'deep'})
            return status=='configured',version
        node=shutil.which('node',path=self.env.get('PATH',''))
        root=None
        cli=self.env.get('REA_CLI_PATH')
        if cli:root=Path(cli).expanduser().resolve().parent.parent
        elif (binary:=shutil.which('rea',path=self.env.get('PATH',''))) and not binary.endswith('.cmd'):
            resolved=Path(binary).resolve()
            if resolved.suffix=='.mjs':root=resolved.parent.parent;cli=str(resolved)
        def rea_probe():
            if not root or not cli:raise ConfigurationRequired('REA is not configured for this app. An agent MCP installation does not configure this process. Set REA_CLI_PATH to the installed rea-agents/scripts/rea.mjs, then restart the app from that terminal.')
            if not Path(cli).is_file():raise FileNotFoundError('REA_CLI_PATH does not point to an existing rea.mjs. Check the path and restart the app.')
            meta=json.loads((root/'package.json').read_text());v=probe([node or 'node','--version'],self.env)
            if not node_compatible(v,meta['engines']['node']):raise ValueError('Installed Node does not satisfy '+meta['engines']['node'])
            self.command=[node or 'node',cli]
            return meta['version'],'Node '+v+'; required '+meta['engines']['node']
        ok,version=row('Node.js + REA','Runs the local reverse engineering adapter.','https://rea.tools/',rea_probe)
        java=Path(self.env['JAVA_HOME'])/'bin'/('java.exe' if os.name=='nt' else 'java') if self.env.get('JAVA_HOME') else shutil.which('java',path=self.env.get('PATH',''))
        def java_probe():
            text=probe([str(java or 'java'),'--list-modules'],self.env)
            m=re.search(r'java.base@(\d+)',text)
            if not m or int(m[1])<17 or 'jdk.compiler@' not in text:raise RuntimeError('A full JDK 17+ including jdk.compiler is required.')
            return m[1],'Compiler module found; APK execution has not been tested.'
        java_ok,_=row('Java JDK','Loads the JADX engine and compiles the metadata bridge.','https://adoptium.net/temurin/releases/',java_probe)
        jar=self.env.get('REA_JADX_MCP_JAR');jar_hash=None
        def jar_probe():
            nonlocal jar_hash
            if not jar:raise ConfigurationRequired('No JADX provider selected for this app. Set REA_JADX_MCP_JAR to the provider JAR and restart the app from that terminal.')
            if not Path(jar).is_file():raise FileNotFoundError('REA_JADX_MCP_JAR does not point to an existing provider JAR.')
            with zipfile.ZipFile(jar) as z:
                names=z.namelist()
                if not any(n.startswith('jadx/') and n.endswith('.class') for n in names):raise ValueError('JAR does not contain JADX classes.')
            jar_hash=digest(jar);return 'JAR selected','SHA-256 '+jar_hash+'; configuration only.'
        jar_ok,_=row('JADX provider JAR','Decodes APK manifests and selected Java methods.',REA_DOC,jar_probe)
        return {'configured':ok and java_ok and jar_ok,'version':version,'jar_sha256':jar_hash,'dependencies':rows}
    def _inspect(self,args,*,cancel=None):
        if cancel and cancel.is_set():raise RuntimeError('Deep analysis cancelled before launch.')
        if not self.command:
            if not self.identity()['configured']:raise RuntimeError('Deep analysis dependencies are unavailable.')
        with tempfile.TemporaryFile() as stdout,tempfile.TemporaryFile() as stderr:
            options={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
            try:p=subprocess.Popen(self.command+args+['--json'],stdout=stdout,stderr=stderr,env=self.env,**options)
            except OSError as e:raise RuntimeError('REA could not start.') from e
            start=time.monotonic();reason=None
            while p.poll() is None:
                if cancel and cancel.is_set():reason='Deep analysis cancelled.';break
                if time.monotonic()-start>self.timeout:reason='REA timed out.';break
                time.sleep(.05)
            if reason:
                try:
                    if os.name=='nt':p.send_signal(signal.CTRL_BREAK_EVENT)
                    else:os.killpg(p.pid,signal.SIGINT)
                    p.wait(timeout=3)
                except (OSError,subprocess.TimeoutExpired):
                    if os.name=='nt':p.kill()
                    else:
                        try:os.killpg(p.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                    p.wait()
                stdout.seek(0);stderr.seek(0)
                observation={'stdout':stdout.read(8*1024*1024).decode(errors='replace'),'stderr':stderr.read(65536).decode(errors='replace'),'interruption':reason}
                raise ReaError(reason+' Owned invocation stopped; interrupted provider cleanup may leave temporary files.',observation)
            stdout.seek(0);stderr.seek(0);raw=stdout.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:raise RuntimeError('REA output exceeded the 8 MiB evidence budget.')
            if p.returncode:
                diagnostic=stderr.read(65536).decode(errors='replace')
                try:observation=json.loads(raw)
                except ValueError:observation={'stdout':raw.decode(errors='replace'),'stderr':diagnostic}
                raise ReaError(diagnostic or ('REA failed: '+str(observation)[:4000]),observation)
            try:result=json.loads(raw)
            except ValueError as e:raise RuntimeError('REA returned invalid JSON.') from e
            if not isinstance(result,dict) or 'normalized_result' not in result:raise ReaError('REA returned an error: '+str(result)[:4000],result)
            return result
    def inspect_package(self,apk,*,cancel=None):return self._inspect(['inspect-android-package',str(apk)],cancel=cancel)
    def inspect_class(self,apk,class_name,*,cancel=None):return self._inspect(['inspect-android-class',str(apk),class_name],cancel=cancel)
    def inspect_method(self,apk,class_name,method_name,*,overload_index=None,cancel=None):
        args=['inspect-android-method',str(apk),class_name,method_name]
        if overload_index is not None:args+=['--overload-index',str(overload_index)]
        return self._inspect(args,cancel=cancel)

def check_prerequisites(adb,rea):
    try:version=adb.version();status='configured';ready=True;detail='Ready for connection authorization.'
    except RuntimeError as e:version=None;status='unavailable';ready=False;detail=str(e)
    ident=rea.identity()
    return {'standard_ready':ready,'deep_configured':ident['configured'],'engine_execution_verified':rea.execution_verified,
            'dependencies':[{'name':'ADB','purpose':'Connects to the TV, inventories packages and applies your previewed choices.','status':status,'version':version,'setup_url':'https://developer.android.com/tools/releases/platform-tools','detail':detail,'required_for':'standard'}]+ident['dependencies']}

def validate_evidence(evidence,sha,engine_sha=None):
    if engine_sha and evidence.get('normalized_result',{}).get('engine',{}).get('artifact_sha256')!=engine_sha:raise ValueError('REA engine hash mismatch; evidence not attributed.')
    if evidence.get('subject',{}).get('digest',{}).get('sha256')!=sha:raise ValueError('REA artifact hash mismatch; evidence not attributed.')

def analyze_inventory(adb,rea,store,inventory,*,on_progress=None,cancel=None):
    inv=copy.deepcopy(inventory);ident=rea.identity();inv['coverage'].update(rea_status='running',rea_successful=0,rea_failed=0)
    if not ident['configured']:inv['coverage']['rea_status']='unavailable';store.save('sessions',inv);return inv
    with tempfile.TemporaryDirectory(prefix='tcl-tv-apk-') as tmp:
        for n,p in enumerate(inv['packages']):
            if cancel and cancel.is_set():inv['coverage']['rea_status']='cancelled';break
            if on_progress:on_progress({'stage':'deep_analysis','completed':n,'total':len(inv['packages']),'message':'Inspecting '+p['package']})
            p['analysis']={'status':'pending','coverage':'base APK only; split set not verified' if len(p['device_paths'])>1 else 'standalone APK; static declarations and reviewed methods only'}
            try:
                paths=p['device_paths']
                base=next((x for x in paths if Path(x).name=='base.apk'),paths[0] if len(paths)==1 else None)
                if not base:raise ValueError('No identifiable base APK; split-set analysis unsupported.')
                apk=Path(tmp)/'target.apk';adb.pull(inv['device']['serial'],base,apk);sha=digest(apk)
                key=json.dumps({'sha':sha,'rea':ident['version'],'jar':ident['jar_sha256'],'operation':'package'},sort_keys=True)
                cached=next((e for e in store.list('evidence') if e.get('cache_key')==key),None)
                evidence=cached['evidence'] if cached else rea.inspect_package(apk,cancel=cancel)
                validate_evidence(evidence,sha,ident['jar_sha256']);normalized=evidence['normalized_result']
                if normalized.get('engine',{}).get('artifact_sha256')!=ident['jar_sha256']:raise ValueError('REA engine hash mismatch; evidence not attributed.')
                if normalized.get('package_name')!=p['package']:raise ValueError('Manifest package mismatch; evidence not attributed.')
                if str(normalized.get('version_code'))!=str(p['version_code']) or normalized.get('version_name')!=p['version_name']:raise ValueError('Manifest version does not match the scanned package.')
                if not cached:
                    cached={**record(),'cache_key':key,'evidence':evidence};store.save('evidence',cached)
                p.update(apk_sha256=sha,declared_permissions=normalized.get('permissions',[]),manifest=normalized.get('manifest',{}),components=normalized.get('components',{}))
                p['evidence']=[cached['id']];p['analysis']['status']='complete';rea.execution_verified=True
                p['analysis']['methods']=[]
                for selector in p.get('reviewed_selectors',[]):
                    if selector['apk_sha256']!=sha:continue
                    class_ev=rea.inspect_class(apk,selector['class_name'],cancel=cancel);validate_evidence(class_ev,sha,ident['jar_sha256'])
                    methods=class_ev['normalized_result'].get('methods',[])
                    candidates=[m for m in methods if m.get('name')==selector['method_name']]
                    index=next((i for i,m in enumerate(candidates) if m.get('reported_signature',m.get('signature'))==selector['signature']),None)
                    if index is None:raise ValueError('Reviewed method signature is unavailable on this artifact.')
                    method_ev=rea.inspect_method(apk,selector['class_name'],selector['method_name'],overload_index=index if len(candidates)>1 else None,cancel=cancel);validate_evidence(method_ev,sha,ident['jar_sha256'])
                    entry={**record(),'cache_key':json.dumps({'sha':sha,'rea':ident['version'],'jar':ident['jar_sha256'],'selector':selector},sort_keys=True),'evidence':method_ev}
                    store.save('evidence',entry);p['evidence'].append(entry['id']);p['analysis']['methods'].append(method_ev['normalized_result'])
                inv['coverage']['rea_successful']+=1
            except (RuntimeError,ValueError,OSError,KeyError) as e:
                p['analysis'].update(status='failed',error=str(e));inv['coverage']['rea_failed']+=1
                if isinstance(e,ReaError) and e.observation is not None:
                    partial={**record(),'status':'failed','request_package':p['package'],'observation':e.observation}
                    store.save('evidence',partial);p['analysis']['partial_evidence_id']=partial['id']
            store.save('sessions',inv)
            if cancel and cancel.is_set():inv['coverage']['rea_status']='cancelled';break
        else:inv['coverage']['rea_status']='partial' if inv['coverage']['rea_failed'] else 'complete'
    store.save('sessions',inv);return inv
