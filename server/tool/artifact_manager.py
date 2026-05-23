import threading
import os

_artifacts_lock = threading.Lock()
_artifacts = {} # filename -> absolute_path

def add_artifact(file_path: str):
    with _artifacts_lock:
        name = os.path.basename(file_path)
        _artifacts[name] = file_path

def get_artifacts():
    with _artifacts_lock:
        return [{"name": k, "path": v} for k, v in _artifacts.items()]
