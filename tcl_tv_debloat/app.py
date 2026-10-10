"""The shared synchronous dispatcher and single background worker."""
import copy,threading
from .inventory import record,scan
from .plans import build_plan,build_restore_plan,execute_plan,export_recovery
from .rea import analyze_inventory
from .store import identifier

PAYLOADS={'connect':{'address'},'pair':{'address','code'},'scan':{'serial','deep'},'analyze':{'inventory_id'},'preview':{'inventory_id','selection'},'apply':{'plan_id'},'restore_preview':{'inventory_id','source_plan_id'},'restore':{'plan_id'},'export':{'plan_id'}}

class Application:
    def __init__(self,adb,store,catalog,rea):
        self.adb=adb;self.store=store;self.catalog=catalog;self.rea=rea
        self._operation_lock=threading.Lock();self._jobs_lock=threading.Lock();self._jobs={};self._cancel={}
    def _validate(self,operation,payload):
        if operation not in PAYLOADS or not isinstance(payload,dict):raise ValueError('Unknown operation or invalid payload.')
        optional={'packages'} if operation=='restore_preview' else ({'privacy_selection'} if operation=='preview' else set())
        if not PAYLOADS[operation].issubset(payload) or not set(payload).issubset(PAYLOADS[operation]|optional):raise ValueError('Invalid operation fields.')
        for k,v in payload.items():
            if k.endswith('_id'):identifier(v)
            elif k in ('address','code','serial') and not isinstance(v,str):raise ValueError('Expected a text value.')
        if operation=='scan' and type(payload['deep']) is not bool:raise ValueError('Deep analysis must be true or false.')
        if operation=='preview' and not isinstance(payload['selection'],dict):raise ValueError('Invalid selection.')
        if 'privacy_selection' in payload and (not isinstance(payload['privacy_selection'],list) or any(not isinstance(x,str) for x in payload['privacy_selection'])):raise ValueError('Invalid privacy selection.')
        if 'packages' in payload and (not isinstance(payload['packages'],list) or any(not isinstance(x,str) for x in payload['packages'])):raise ValueError('Invalid package list.')
    def _dispatch(self,operation,payload,*,on_progress=None,cancel=None):
        self._validate(operation,payload)
        if operation=='connect':return {'message':self.adb.connect(payload['address'])}
        if operation=='pair':self.adb.pair(payload['address'],payload['code']);return {'message':'Pairing completed. Connect using the TV connection port.'}
        if operation=='scan':
            inv=scan(self.adb,payload['serial'],self.catalog,on_progress=on_progress,cancel=cancel);self.store.save('sessions',inv)
            if payload['deep'] and inv['status']!='cancelled':inv=analyze_inventory(self.adb,self.rea,self.store,inv,on_progress=on_progress,cancel=cancel)
            return inv
        if operation=='analyze':return analyze_inventory(self.adb,self.rea,self.store,self.store.load('sessions',payload['inventory_id']),on_progress=on_progress,cancel=cancel)
        if operation=='preview':
            p=build_plan(self.store.load('sessions',payload['inventory_id']),payload['selection'],privacy_selection=payload.get('privacy_selection'));self.store.save('plans',p);return p
        if operation=='restore_preview':
            p=build_restore_plan(self.store.load('sessions',payload['inventory_id']),self.store.load('plans',payload['source_plan_id']),payload.get('packages'));self.store.save('plans',p);return p
        p=self.store.load('plans',payload['plan_id'])
        if operation=='export':return export_recovery(p)
        if p['mode']!=('apply' if operation=='apply' else 'restore'):raise ValueError('Plan mode does not match this operation.')
        return execute_plan(self.adb,self.store,self.catalog,p,on_progress=on_progress,cancel=cancel)
    def run(self,operation,payload,*,on_progress=None,cancel=None):
        if not self._operation_lock.acquire(blocking=False):raise RuntimeError('Another operation is busy.')
        try:return self._dispatch(operation,payload,on_progress=on_progress,cancel=cancel)
        finally:self._operation_lock.release()
    def start(self,operation,payload):
        self._validate(operation,payload)
        if not self._operation_lock.acquire(blocking=False):raise RuntimeError('Another operation is busy.')
        job=record();ident=job['id'];job.update(operation=operation,status='running',stage='starting',completed=0,total=None,message='Starting '+operation,result_id=None,error=None)
        stop=threading.Event()
        with self._jobs_lock:self._jobs[ident]=job;self._cancel[ident]=stop
        def progress(value):
            with self._jobs_lock:job.update(value)
        def worker():
            try:
                result=self._dispatch(operation,payload,on_progress=progress,cancel=stop)
                with self._jobs_lock:
                    job['result_id']=result.get('id');job['result']=result if not result.get('id') else None
                    job['status']='cancelled' if result.get('status')=='cancelled' or result.get('coverage',{}).get('rea_status')=='cancelled' else ('failed' if result.get('status')=='failed' else 'complete')
                    job['message']='Operation '+job['status']+'.'
            except Exception as e:
                with self._jobs_lock:job.update(status='failed',error=str(e),message='Operation failed.')
            finally:self._operation_lock.release()
        threading.Thread(target=worker,daemon=True).start();return ident
    def status(self,job_id):
        identifier(job_id)
        with self._jobs_lock:
            if job_id not in self._jobs:raise KeyError('Job not found in this launch. Saved history remains available.')
            return copy.deepcopy(self._jobs[job_id])
    def cancel(self,job_id):
        self.status(job_id);self._cancel[job_id].set()
