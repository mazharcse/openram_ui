# config_loader.py
import importlib.util
import os

def _load_config_file(path):
    """Dynamically loads a Python config file into a dictionary."""
    config = {}
    if not os.path.exists(path):
        return config

    # Get the absolute path to the config file
    abs_path = os.path.abspath(path)
    
    spec = importlib.util.spec_from_file_location("config", abs_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for key in dir(module):
        if not key.startswith("__"):
            config[key] = getattr(module, key)
    return config

def load_config(personal_config_path, default_config_path="config/default.py"):
    """
    Loads the default and personal configurations and merges them.
    Personal config values override default values.
    """
    default_config = _load_config_file(default_config_path)
    personal_config = _load_config_file(personal_config_path)

    # Merge the two configurations
    merged_config = {**default_config, **personal_config}
    
    return merged_config