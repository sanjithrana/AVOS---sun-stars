"""Start the AVOS GPU worker with any Python, e.g. ComfyUI portable's embedded one (which ignores PYTHONPATH and the
current folder):  python_embeded\\python.exe -s apps\\gpu_worker\\run_worker.py"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
runpy.run_module("worker", run_name="__main__")
