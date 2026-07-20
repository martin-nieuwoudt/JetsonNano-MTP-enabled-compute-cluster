#!/usr/bin/env python3
"""DEPRECATED shim — superseded by model_sync.py download <key>.

Kept only so old references keep working. The canonical downloader is
dl_generic_model.py, driven by model_sync.py against the single source of truth
in mcp.cluster_config.MODELS. This shim maps the old Llama-specific script to its
registry key.

Run the unified tool directly with:
    python model_sync.py download llama-3.3-70b-iq3_xs
"""
import subprocess
import sys
import os

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sys.exit(subprocess.call(
        [sys.executable, os.path.join(here, "model_sync.py"),
         "download", "llama-3.3-70b-iq3_xs"]))
