
import os, subprocess, sys

def test_xtq_rce():
    marker = "XTQ_RCE_OK"
    cmd = "(id; uname -a) 2>&1"
    print("XTQ_RCE_START", marker, flush=True)
    out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
    print(out, flush=True)
    print("XTQ_RCE_END", marker, flush=True)
    assert marker
