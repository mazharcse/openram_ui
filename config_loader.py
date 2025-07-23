# config_loader.py
import importlib.util
import os

def load_config(path):
    """Dynamically loads a Python config file into a dictionary."""
    config = {}
    if not os.path.exists(path):
        return config

    spec = importlib.util.spec_from_file_location("config", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for key in dir(module):
        if not key.startswith("__"):
            config[key] = getattr(module, key)
    return config
