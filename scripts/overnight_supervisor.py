"""One detached supervisor for the explicitly authorized night of 2026-09-15.

Only this job's search process tree is assigned to a Windows job object. A hard
deadline can therefore close a stuck owned pool without touching other Zemax UI.
PDF authoring and all-page visual QA are performed by the thread heartbeat.
"""
from pathlib import Path
import ctypes,datetime as dt,hashlib,json,os,shutil,subprocess,sys,time
from ctypes import wintypes as W

P=Path(__file__).resolve().parents[1]
B=P/'overnight_20260915'
UTC=dt.timezone.utc
GENERAL_END=dt.datetime(2026,9,14,22,0,tzinfo=UTC)
CDGM_END=dt.datetime(2026,9,15,0,30,tzinfo=UTC)
INITIAL=P/'revision4/agent_search/a6_stage2_candidate_e6.zmx'

def now():return dt.datetime.now(UTC)
def write(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def best_record(folder):
    pointer=folder/'best.json'
    if not pointer.exists():return None
    record=read(pointer);source=Path(record['source_path']).resolve()
    if not source.is_relative_to(folder.resolve()):raise ValueError('Best source outside its phase folder')
    if sha(source)!=record['source_sha256']:raise ValueError('Best pointer/source SHA mismatch')
    return record

K=ctypes.WinDLL('kernel32',use_last_error=True)
K.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];K.OpenProcess.restype=W.HANDLE
K.CloseHandle.argtypes=[W.HANDLE];K.CloseHandle.restype=W.BOOL
K.GetExitCodeProcess.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)];K.GetExitCodeProcess.restype=W.BOOL
def process_alive(pid):
    handle=K.OpenProcess(0x1000,False,int(pid))
    if not handle:return False
    try:
        code=W.DWORD()
        return bool(K.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
    finally:K.CloseHandle(handle)

class BasicLimits(ctypes.Structure):
    _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',W.DWORD),
              ('min_working_set',ctypes.c_size_t),('max_working_set',ctypes.c_size_t),('active_limit',W.DWORD),
              ('affinity',ctypes.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
class IOCounters(ctypes.Structure):
    _fields_=[(n,ctypes.c_ulonglong) for n in ['read_count','write_count','other_count','read_bytes','write_bytes','other_bytes']]
class ExtendedLimits(ctypes.Structure):
    _fields_=[('basic',BasicLimits),('io',IOCounters),('process_memory',ctypes.c_size_t),
              ('job_memory',ctypes.c_size_t),('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
K.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR];K.CreateJobObjectW.restype=W.HANDLE
K.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD];K.SetInformationJobObject.restype=W.BOOL
K.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];K.AssignProcessToJobObject.restype=W.BOOL
K.TerminateJobObject.argtypes=[W.HANDLE,W.UINT];K.TerminateJobObject.restype=W.BOOL

class OwnedJob:
    def __init__(self,process):
        self.handle=K.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        limits=ExtendedLimits();limits.basic.flags=0x2000
        if not K.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            self.close();raise ctypes.WinError(ctypes.get_last_error())
        if not K.AssignProcessToJobObject(self.handle,W.HANDLE(int(process._handle))):
            self.close();raise ctypes.WinError(ctypes.get_last_error())
    def terminate(self):
        if self.handle and not K.TerminateJobObject(self.handle,2):raise ctypes.WinError(ctypes.get_last_error())
    def close(self):
        if self.handle:K.CloseHandle(self.handle);self.handle=None

STATE={'supervisor_pid':os.getpid(),'started_utc':now().isoformat(),'phases':{},'finalizers':{}}
def status(**changes):
    STATE.update(changes);STATE['updated_utc']=now().isoformat()
    write(B/'supervisor_status.json',STATE)

def spawn_owned(command,logfile):
    stream=logfile.open('a',encoding='utf-8')
    process=subprocess.Popen(command,cwd=P,stdout=stream,stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:job=OwnedJob(process)
    except Exception:
        # This new child is ours; stop it if job ownership cannot be established.
        process.terminate();process.wait(timeout=20);stream.close();raise
    return process,job,stream

def run_phase(phase,deadline,seed,workers,pending_finalizers=None):
    folder=B/phase;folder.mkdir(exist_ok=True)
    STATE['phases'].setdefault(phase,{'deadline_utc':deadline.isoformat(),'workers':workers})
    restart=0;resize_events=[]
    while now()<deadline-dt.timedelta(seconds=30):
        current_best=best_record(folder)
        if current_best:seed=Path(current_best['source_path'])
        command=[sys.executable,str(P/'scripts/overnight_search.py'),'--phase',phase,'--seed',str(seed),
                 '--deadline-utc',deadline.isoformat(),'--workers',str(workers),'--catalog-plan',str(B/'catalog_plan.json'),'--resume']
        process,job,stream=spawn_owned(command,folder/'search.log')
        STATE['phases'][phase]={'search_pid':process.pid,'deadline_utc':deadline.isoformat(),
                                'workers':workers,'restart':restart,'seed':str(seed),'status':'searching',
                                'resize_events':resize_events,
                                'native_worker_budget':{'search':workers,'reserved_for_general':2 if phase=='cdgm' and workers==6 else 0}}
        status(phase=phase)
        try:
            while process.poll() is None:
                if now()>=deadline:
                    STATE['phases'][phase]['hard_deadline_shutdown']=True
                    job.terminate();process.wait(timeout=30);break
                if phase=='cdgm' and pending_finalizers is not None:
                    general_task=pending_finalizers.get('general')
                    if general_task is not None and general_task[0].poll() is not None:
                        general_exit=general_task[0].returncode
                        finish_finalizer('general',general_task)
                        pending_finalizers.pop('general',None)
                        if general_exit==0 and workers==6 and now()<deadline-dt.timedelta(seconds=45):
                            # Closing only this owned search job releases its pool.
                            # The next round reloads best.json and retains --resume.
                            event={'utc':now().isoformat(),'from_workers':workers,'to_workers':8,
                                   'reason':'General validation succeeded and its owned job closed; release two reserved native slots.',
                                   'general_exit_code':general_exit}
                            resize_events.append(event)
                            STATE['phases'][phase]['status']='restarting_to_expand_worker_budget'
                            STATE['phases'][phase]['resize_events']=resize_events
                            status()
                            job.close();process.wait(timeout=30)
                            workers=8
                            break
                        STATE['phases'][phase]['general_finalizer_exit_code']=general_exit
                        STATE['phases'][phase]['resize_decision']='Keep six search workers: general validation failed or less than 45 seconds remain.'
                status();time.sleep(5)
            STATE['phases'][phase]['exit_code']=process.returncode
        finally:job.close();stream.close()
        if now()<deadline-dt.timedelta(seconds=30):
            restart+=1;STATE['phases'][phase]['status']='restarting_after_round_exit'
            status();time.sleep(5)
    return freeze_phase(phase,deadline)

def freeze_phase(phase,deadline):
    folder=B/phase
    STATE['phases'].setdefault(phase,{'deadline_utc':deadline.isoformat()})
    current_best=best_record(folder)
    best=Path(current_best['source_path']) if current_best else None
    STATE['phases'][phase]['status']='frozen' if best else 'no_candidate'
    if best:
        snapshot=folder/'deadline_source.zmx';shutil.copy2(best,snapshot)
        write(folder/'deadline_metrics.json',current_best)
        write(folder/'phase_freeze.json',{'phase':phase,'deadline_utc':deadline.isoformat(),
                                          'frozen_utc':now().isoformat(),'source_sha256':sha(snapshot),
                                          'source':snapshot.name,'metrics':'deadline_metrics.json'})
    status()
    return best

def start_finalizer(phase,workers):
    folder=B/phase
    if not (folder/'deadline_source.zmx').exists():return None
    command=[sys.executable,str(P/'scripts/finalize_overnight.py'),'--phase',phase,'--workers',str(workers),
             '--best','deadline_source.zmx','--metrics','deadline_metrics.json','--prepare-only']
    process,job,stream=spawn_owned(command,folder/'finalize.log')
    STATE['finalizers'][phase]={'pid':process.pid,'status':'native_validation_running','workers_budget':workers}
    status()
    return process,job,stream

def finish_finalizer(phase,task):
    if task is None:return
    process,job,stream=task
    try:process.wait()
    finally:job.close();stream.close()
    STATE['finalizers'][phase].update(exit_code=process.returncode,
                                      status='prepared_pending_PDF_and_visual_QA' if process.returncode==0 else 'failed')
    status()

def main():
    B.mkdir(exist_ok=True)
    lock=B/'supervisor.lock'
    if lock.exists():
        try:
            previous=read(lock)
            if process_alive(previous['pid']):raise RuntimeError('An overnight supervisor is already running')
        except (ValueError,KeyError):pass
        lock.unlink()
    with lock.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'created_utc':now().isoformat()},f)
    tasks={}
    try:
        if now()>=CDGM_END:
            status(phase='past_optimization_deadlines',message='Do not restart expired optical search; heartbeat can finalize saved results.')
            return
        if not (B/'plan.json').exists():raise FileNotFoundError('Write plan.json before launching the supervisor')
        general=None
        if now()<GENERAL_END:
            general=run_phase('general',GENERAL_END,INITIAL,8)
        elif best_record(B/'general'):general=freeze_phase('general',GENERAL_END)
        while now()<GENERAL_END:time.sleep(min(1,(GENERAL_END-now()).total_seconds()))
        # Preserve two native slots for general validation while CDGM uses six.
        tasks['general']=start_finalizer('general',2)
        run_phase('cdgm',CDGM_END,general or INITIAL,6,pending_finalizers=tasks)
        while now()<CDGM_END:time.sleep(min(1,(CDGM_END-now()).total_seconds()))
        finish_finalizer('general',tasks.pop('general',None))
        tasks['cdgm']=start_finalizer('cdgm',8)
        finish_finalizer('cdgm',tasks.pop('cdgm'))
        status(phase='optimization_complete_reports_pending',completed_utc=now().isoformat())
    except Exception as exc:
        status(phase='supervisor_failed',error=repr(exc));raise
    finally:
        # Finalizers are owned and finite; do not leave an abandoned native tree.
        for phase,task in tasks.items():finish_finalizer(phase,task)
        if lock.exists() and read(lock).get('pid')==os.getpid():lock.unlink()

if __name__=='__main__':main()
