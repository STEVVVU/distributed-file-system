"""Native guarded SeaweedFS HTTP load with byte/range and cleanup oracles."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import stat
import sys
import time
import urllib.error

from benchmark_support import Run, environment, load, save
from verify import ROOT, Workbench

WORKLOAD=dict(version=2,seed=421,sizes=[4096,1048576,16777216],concurrency=[1,4,16],operations=['put','get','metadata'],repeats=5,count=16,large_count=4,rates=[5,20,80],sweep_seconds=10,stability_seconds=120,storage_phase='after all owned writers stop, before guarded deletion')


def payload(size):
    block=bytes((i+WORKLOAD['seed'])%256 for i in range(256))
    return (block*((size+255)//256))[:size]


def baseport():
    for _ in range(100):
        base=20000+secrets.randbelow(20000)
        reservations=[]
        try:
            for number in [base+i+offset for i in range(6) for offset in [0,10000]]:
                sock=socket.socket();reservations.append(sock);sock.bind(('127.0.0.1',number))
            return base
        except OSError:pass
        finally:
            for sock in reservations:sock.close()
    raise RuntimeError('no owned free HTTP/gRPC port range')


class Bench(Workbench):
    def before_remove_data(self,target):
        if target!=self.owned_data or not hasattr(self,'storage_live_payload_bytes'):
            return
        assert not self.processes,'storage snapshot requires every owned writer to be reaped'
        entries=[file.lstat() for file in target.rglob('*')]
        files=[entry for entry in entries if stat.S_ISREG(entry.st_mode)]
        self.storage=dict(apparent_bytes=sum(entry.st_size for entry in files),allocated_bytes=sum(getattr(entry,'st_blocks',0)*512 for entry in files) if os.name!='nt' else None,live_payload_bytes=self.storage_live_payload_bytes)
        self.storage['scope']='Whole owned master/filer/volume regular-file tree after every owned process is reaped, before guarded deletion. Includes indexes, replication and retained deleted needles; Linux allocated blocks only. This differs from version-1 live-tree sampling.'

    def start(self,name,arguments):
        if self.args.profile and (name=='master' or name.startswith('volume-')):
            arguments=[*arguments,f'-cpuprofile={self.out.resolve()/ (name+".pprof")}']
        super().start(name,arguments)
        if hasattr(self,'sampler'):
            self.sampler.processes=list(self.processes.items())


def trial(cell,count,rate=None,recovery=False,profile=False):
    assert shutil.disk_usage(ROOT).free>=10*1024**3,'10GiB free disk required'
    args=argparse.Namespace(binary=ROOT/'.local/weed.exe',run='benchmark-trial-'+str(time.time_ns()),port=baseport(),fail=False,scenario='baseline',profile=profile)
    bench=Bench(args)
    sampler=Run(bench.out/'benchmark')
    bench.sampler=sampler
    result=dict(passed=False,cell=cell,rate=rate,recovery=recovery,evidence=str(bench.out))
    completed=False
    try:
        bench.launch()
        data=payload(cell['size']);digest=hashlib.sha256(data).hexdigest()
        result.update(payload_sha256=digest,payload_bytes=len(data))
        warm='/benchmark/warm.bin'
        bench.upload(warm,data);bench.verify_bytes(warm,data,'untimed-warmup-oracle')
        def put(path):
            status,body,_=bench.request(bench.filer,path,'PUT',data,{'Content-Type':'application/octet-stream'},timeout=30)
            assert status in (200,201),(status,body)
            return dict(status=status,response=json.loads(body),bytes=len(data),path=path)
        def get(path):
            status,actual,_=bench.request(bench.filer,path,timeout=30)
            assert status==200 and len(actual)==len(data) and hashlib.sha256(actual).hexdigest()==digest,'full byte oracle failed'
            return dict(status=status,bytes=len(actual),sha256=digest,path=path)
        def delete(path):
            status,_,_=bench.request(bench.filer,path,'DELETE')
            assert status in (200,202,204),status
            try:bench.request(bench.filer,path)
            except urllib.error.HTTPError as error:assert error.code==404
            else:raise AssertionError('deleted path remains readable')
        def action(index):
            path=f'/benchmark/object-{index}.bin'
            if cell['operation']=='put':return put(path)
            if cell['operation']=='get':return get(warm)
            if cell['operation']=='lifecycle':
                put(path);proof=get(path);delete(path);return proof
            status,body,_=bench.request(bench.filer,warm+'?metadata=true')
            metadata=json.loads(body);assert status==200 and isinstance(metadata,dict)
            status,listing,_=bench.request(bench.filer,'/benchmark/?pretty=y',headers={'Accept':'application/json'})
            assert status==200 and b'warm.bin' in listing
            return dict(stat_sha256=hashlib.sha256(body).hexdigest(),listing_sha256=hashlib.sha256(listing).hexdigest(),requests=2)
        result['load']=load(action,count,cell['concurrency'],rate)
        result['useful_bytes']=result['load']['finished']*len(data) if cell['operation'] in ('put','get','lifecycle') else 0
        if cell['operation']=='lifecycle':result['bandwidth_scope']='One verified PUT+GET+DELETE lifecycle per offer; useful_bytes is one payload, separate from bidirectional network bytes.'
        if cell['operation']=='put':
            successes=[s for s in result['load']['samples'] if s['outcome']=='finished']
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(cell['concurrency'],4)) as pool:list(pool.map(lambda s:get(s['proof']['path']),successes))
            result['verified_write_count']=len(successes)
        start=max(0,len(data)//2-10);end=min(len(data)-1,start+20)
        status,actual,_=bench.request(bench.filer,warm,headers={'Range':f'bytes={start}-{end}'})
        assert status==206 and actual==data[start:end+1],'range oracle failed'
        metadata=json.loads(bench.request(bench.filer,warm+'?metadata=true')[1]);result['manifest']=metadata
        bench.storage_live_payload_bytes=len(data)*(1+(result['load']['finished'] if cell['operation']=='put' else 0))
        if recovery:
            chunks=metadata.get('chunks',[]);assert len(chunks)>1
            result['recovery_start']=time.perf_counter();bench.recovery(warm,data,chunks);result['recovery_end']=time.perf_counter()
            result['repair']=bench.result['repair']
        completed=result['load']['finished']==count
    except Exception as error:result.update(error=repr(error),error_detail=str(error))
    finally:
        bench.finish(completed)
        if hasattr(bench,'storage'):result['storage']=bench.storage
        sampler.processes=[]
        result['sampler_cleanup']=sampler.cleanup()
        result['cleanup']=bench.result['cleanup']
        result['cleanup_errors']=bench.result.get('cleanup_errors',[])
        result['passed']=completed and result['cleanup'] and result['sampler_cleanup']['sampler_stopped']
        if profile:
            result['profiles']=[file.name for file in bench.out.glob('*.pprof') if file.stat().st_size]
            result['profile_scope']='Native master and volume CPU profiles; filer has no enabled loopback-safe hot-path profile here. Generator cProfile captured separately. Profiles excluded from comparisons.'
            result['passed']=result['passed'] and len(result['profiles'])>=4
        save(bench.out/'benchmark'/'result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['smoke','benchmark','profile'],default='smoke',nargs='?');args=parser.parse_args()
    assert args.mode=='smoke' or sys.platform=='linux','isolated Linux required'
    directory=ROOT/'.local'/('benchmark-'+args.mode+'-'+str(time.time_ns()));directory.mkdir(parents=True)
    summary=dict(passed=False,mode=args.mode,environment=environment(ROOT),workload=WORKLOAD,trials=[])
    def run(cell,count=WORKLOAD['count'],rate=None,recovery=False):
        value=trial(cell,count,rate,recovery,args.mode=='profile');summary['trials'].append(value);save(directory/'summary.json',summary)
        print(json.dumps(dict(passed=value['passed'],evidence=value['evidence'])),flush=True)
        if value.get('error') or not value['cleanup']:raise RuntimeError(value.get('error','cleanup failed'))
        return value
    try:
        if args.mode=='smoke':run(dict(size=4096,concurrency=1,operation='lifecycle'),1)
        elif args.mode=='profile':
            import cProfile
            profiler=cProfile.Profile();profiler.enable();run(dict(size=1048576,concurrency=4,operation='put'));profiler.disable();profiler.dump_stats(str(directory/'generator.pstats'))
        else:
            matrix=[dict(size=size,concurrency=concurrency,operation=operation) for size in WORKLOAD['sizes'] for concurrency in WORKLOAD['concurrency'] for operation in WORKLOAD['operations']]
            for repeat in range(WORKLOAD['repeats']):
                for cell in matrix if repeat%2==0 else reversed(matrix):run(dict(cell,repeat=repeat),WORKLOAD['large_count'] if cell['size']==16777216 else WORKLOAD['count'])
            base=dict(size=4096,concurrency=16,operation='lifecycle')
            sweeps=[run(base,rate*WORKLOAD['sweep_seconds'],rate) for rate in WORKLOAD['rates']]
            stable=[v for v in sweeps if v['passed'] and v['load']['dispatch_lag_ms']['p99']<100 and v['load']['latency_ms']['p99']<5000]
            if stable:
                rate=stable[-1]['rate'];run(base,rate*WORKLOAD['stability_seconds'],rate)
            else:summary['stability_blocked']='No qualifying zero-loss offered rate; retain sweep and expand lower rates.'
            run(dict(size=1048576*2,concurrency=1,operation='get'),1,recovery=True)
        summary['passed']=all(v['passed'] for v in summary['trials']) and not summary.get('stability_blocked')
    except Exception as error:summary['error']=repr(error)
    finally:save(directory/'summary.json',summary)
    print(directory/'summary.json');return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
