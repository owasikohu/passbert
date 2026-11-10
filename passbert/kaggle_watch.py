"""Bounded fresh-process status polling avoids a stalled long-lived SDK request."""
import re
import subprocess

def kernel_status(cli,kernel,timeout=45):
    response=subprocess.run([cli,'kernels','status',kernel],capture_output=True,text=True,check=True,timeout=timeout)
    match=re.search(r'KernelWorkerStatus\.([A-Z_]+)',response.stdout)
    if match is None:raise ValueError('Unrecognized Kaggle status output')
    return match[1].lower()
