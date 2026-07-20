#!/usr/bin/env python3
"""Backward-compatible wrapper.

cluster_monitor.py is now merged into cluster_telemetry.py. This shim preserves
the old live terminal-monitor entry point. Run the unified tool directly with:
    python cluster_telemetry.py monitor
"""
import subprocess
import sys
import os

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sys.exit(subprocess.call([sys.executable, os.path.join(here, "cluster_telemetry.py"), "monitor"]))