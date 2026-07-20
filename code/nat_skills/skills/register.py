"""register.py — NAT plugin entry point.

Declared in pyproject.toml under [project.entry-points.'nat.plugins'] as
    cluster_skills = "skills.register"

Importing this module loads every @register_function decorator so NeMo Agent
Toolkit discovers the custom skills when `nat` starts.
"""
from . import phase2_methods  # registers phase2_method, phase2_list_methods
from . import recursive_entropy  # registers recursive_entropy_optimize
