from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# Gunakan SQLite untuk development
SQLALCHEMY_DATABASE_URL = "sqlite:///./smartjemuran.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Buat tabel jika belum ada
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()