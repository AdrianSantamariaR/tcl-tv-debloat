"""Private, versioned JSON and a cross-process mutation lock."""
import hashlib, json, os, tempfile, uuid
from pathlib import Path
from contextlib import contextmanager

KINDS={'sessions','plans','evidence'}
def recovery_digest(record):
    """Checksum of the original states; progress and outcomes may change."""
    original={key:record.get(key) for key in ('schema_version','id','inventory_id','device','mode','target_user','source_plan_id')}
    for key in ('changes','setting_changes'):
        original[key]=[{k:v for k,v in change.items() if k not in ('outcome','diagnostic')} for change in record.get(key,[])]
    return hashlib.sha256(json.dumps(original,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def verified_recovery(record):
    if record.get('status') not in ('running','complete','failed','cancelled'):return False
    # Journals written before recovery metadata was introduced remain compatible.
    if 'recovery_status' not in record and 'recovery_digest' not in record:return True
    if record.get('recovery_status')!='verified' or not isinstance(record.get('recovery_digest'),str):return False
    try:return record['recovery_digest']==recovery_digest(record)
    except (TypeError,ValueError,AttributeError):return False

def identifier(value):
    if not isinstance(value,str) or str(uuid.UUID(value))!=value: raise ValueError('Invalid record ID.')
    return value

class Store:
    def __init__(self, root: Path):
        self.root=Path(root).expanduser().resolve();self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        if os.name!='nt':self.root.chmod(0o700)
        for k in KINDS: (self.root/k).mkdir(exist_ok=True,mode=0o700)
    def _path(self,kind,ident):
        if kind not in KINDS:raise ValueError('Unknown record kind.')
        return self.root/kind/(identifier(ident)+'.json')
    def save(self,kind,record):
        if record.get('schema_version')!=1:raise ValueError('Unsupported schema version.')
        dest=self._path(kind,record['id'])
        fd,tmp=tempfile.mkstemp(dir=dest.parent,prefix='.writing-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(record,f,indent=2,ensure_ascii=False);f.flush();os.fsync(f.fileno())
            os.replace(tmp,dest)
            if os.name!='nt':
                directory=os.open(dest.parent,os.O_RDONLY)
                try:os.fsync(directory)
                finally:os.close(directory)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return record['id']
    def load(self,kind,ident):
        r=json.loads(self._path(kind,ident).read_text(encoding='utf-8'))
        if r.get('schema_version')!=1 or r.get('id')!=ident:raise ValueError('Unsupported or inconsistent record.')
        if kind=='plans' and ('recovery_status' in r or 'recovery_digest' in r) and r.get('recovery_status')!='pending' and not verified_recovery(r) and r.get('status')!='recovery_failed':
            r['status']='recovery_invalid';r['recovery_status']='failed'
            r['recovery_error']='Recorded original states do not match checked recovery.'
        return r
    def save_verified(self,kind,record):
        """A recovery record must survive a disk read before any device write."""
        try:
            self.save(kind,record)
            if self.load(kind,record['id'])!=record:
                raise ValueError('Saved contents do not match the recovery record.')
        except (OSError,ValueError) as error:
            raise RuntimeError('Recovery point could not be saved and checked. No TV changes were sent. '+str(error)) from error
        return record['id']
    def list(self,kind):
        if kind not in KINDS:raise ValueError('Unknown record kind.')
        return sorted((self.load(kind,p.stem) for p in (self.root/kind).glob('*.json')),key=lambda r:r.get('created_at',r.get('captured_at','')),reverse=True)
    @contextmanager
    def mutation_lock(self):
        path=self.root/'mutation.lock'
        fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
        with os.fdopen(fd,'r+b') as f:
            if not path.stat().st_size:f.write(b'0');f.flush()
            try:
                if os.name=='nt':
                    import msvcrt
                    f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise RuntimeError('Another operation holds the mutation lock.') from None
            try:yield
            finally:
                if os.name=='nt':f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)
