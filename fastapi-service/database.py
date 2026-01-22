from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 連接到 Docker 中的 PostgreSQL
# 如果你的 Python 程式是在本機執行，請用 localhost
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/tongue_ai_memory"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
