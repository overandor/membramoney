from __future__ import annotations

from _bootstrap import bootstrap_project_root

bootstrap_project_root()

from app.main import run


if __name__ == "__main__":
    raise SystemExit(run())
