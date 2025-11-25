"""Configuration package - centralized settings management.

Temporary backward compatibility: Re-exports from parent-level config module.
This will be replaced in Phase 3-B with proper package structure.
"""

import importlib.util
from pathlib import Path

# Explicitly load the config.py module file from parent directory
_config_module_path = Path(__file__).parent.parent / "config.py"
_spec = importlib.util.spec_from_file_location("_src_config_module", _config_module_path)
if _spec and _spec.loader:
    _config_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_config_module)
    
    # Re-export AppConfig
    AppConfig = _config_module.AppConfig
    
    __all__ = ["AppConfig"]
else:
    raise ImportError(f"Could not load config module from {_config_module_path}")
