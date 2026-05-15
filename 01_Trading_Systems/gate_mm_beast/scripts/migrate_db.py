from app.config import Settings
from app.persistence.db import Database

if __name__ == "__main__":
    Database(Settings().db_path)
    print("database initialized")
