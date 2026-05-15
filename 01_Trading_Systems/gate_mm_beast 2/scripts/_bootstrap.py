from __future__ import annotations

import os
import sys
from pathlib import Path


def bootstrap_project_root() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    os.chdir(project_root)
    return project_root
