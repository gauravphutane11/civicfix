from pathlib import Path
from .database import Base, engine, SessionLocal
from .seed import seed_if_empty, ensure_demo_admin

if __name__ == "__main__":
    db_path = Path(__file__).resolve().parent.parent / "civicfix.db"
    if db_path.exists():
        db_path.unlink()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
        ensure_demo_admin(db)
        db.commit()
        print("CivicFix demo database reset and seeded.")
    finally:
        db.close()
