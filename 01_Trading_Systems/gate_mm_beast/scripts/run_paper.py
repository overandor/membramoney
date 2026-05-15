import os
os.environ["MODE"] = "paper"
from app.main import run

if __name__ == "__main__":
    raise SystemExit(run())
