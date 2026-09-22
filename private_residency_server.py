"""Private idle-server CUDA storage parking; no policy/history/RNG reset.

Only used by the isolated video coordinator. Preserve tensor identity, dtype,
shape, strides, offsets and shared-storage aliases across CPU/GPU movement.
Requests that could run inference are refused while this process is parked.
"""
import argparse
import gc
from pathlib import Path
import runpy
import sys


class Residency:
    def __init__(self, torch):
        self.torch=torch;self.parked=None;self.device=None

    def move(self, tensors, device):
        torch=self.torch
        storage_copies={};specs=[]
        with torch.no_grad():
            for tensor in tensors:
                if tensor.layout != torch.strided:
                    raise RuntimeError('Unsupported non-strided CUDA state')
                storage=tensor.untyped_storage()
                key=(storage.data_ptr(),storage.nbytes(),str(tensor.device))
                if key not in storage_copies:
                    byteview=torch.empty(0,dtype=torch.uint8,device=tensor.device).set_(
                        storage,0,(storage.nbytes(),),(1,))
                    storage_copies[key]=byteview.to(device=device,copy=True).untyped_storage()
                specs.append((tensor,key,tensor.storage_offset(),tuple(tensor.shape),tuple(tensor.stride()),tensor.dtype))
            for tensor,key,offset,shape,strides,dtype in specs:
                replacement=torch.empty(0,dtype=dtype,device=device).set_(
                    storage_copies[key],offset,shape,strides)
                tensor.data=replacement
        return dict(tensors=len(tensors),storages=len(storage_copies),
                    bytes=sum(s.nbytes() for s in storage_copies.values()))

    def park(self):
        torch=self.torch
        if self.parked is not None:return dict(parked=True,already=True)
        torch.cuda.synchronize();gc.collect()
        tensors=[]
        for obj in gc.get_objects():
            try:
                if isinstance(obj,torch.Tensor) and obj.device.type=='cuda':tensors.append(obj)
            except (ReferenceError,RuntimeError):pass
        devices={str(t.device) for t in tensors}
        if len(devices)!=1:raise RuntimeError(f'Expected one private CUDA device: {devices}')
        self.device=next(iter(devices))
        result=self.move(tensors,'cpu');self.parked=tensors
        gc.collect();torch.cuda.empty_cache()
        result.update(parked=True,cuda_allocated_bytes=torch.cuda.memory_allocated())
        return result

    def resume(self):
        if self.parked is None:return dict(parked=False,already=True)
        result=self.move(self.parked,self.device)
        self.torch.cuda.synchronize();self.parked=None;gc.collect()
        result.update(parked=False,cuda_allocated_bytes=self.torch.cuda.memory_allocated())
        return result


def main():
    import torch
    from flask import Flask,request
    sys.path.insert(0,'/home/asus/Research/Nav-graph-blind')
    from MemNavData.private_gpu_cache_server import install
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--entrypoint',required=True)
    args,rest=ap.parse_known_args();original=Flask.run
    residency=Residency(torch)
    def run(app,*a,**kw):
        install(app,torch.cuda)
        app.add_url_rule('/private_park','private_park',residency.park,methods=['POST'])
        app.add_url_rule('/private_resume','private_resume',residency.resume,methods=['POST'])
        @app.before_request
        def parked_guard():
            if residency.parked is not None and not request.path.startswith('/private_'):
                return dict(error='Private process is parked; coordinator must resume it'),409
        return original(app,*a,**kw)
    Flask.run=run;sys.argv=[args.entrypoint,*rest]
    runpy.run_path(args.entrypoint,run_name='__main__')


if __name__=='__main__':main()
