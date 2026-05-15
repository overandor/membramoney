from __future__ import annotations

import os

from _bootstrap import bootstrap_project_root

bootstrap_project_root()
os.environ["MODE"] = "replay"

from app.main import run


if __name__ == "__main__":
    raise SystemExit(run())
