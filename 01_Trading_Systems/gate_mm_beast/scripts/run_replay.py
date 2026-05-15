import os
os.environ["MODE"] = "replay"
from app.main import run

if __name__ == "__main__":
    raise SystemExit(run())
