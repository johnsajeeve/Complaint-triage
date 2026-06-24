"""
Database connection and session management.

This module handles:
1. Creating a connection to Postgres
2. Creating tables
3. Providing a session for queries
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read database credentials from .env
# (These match what we set in docker-compose.yml)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "complaints")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# Construct the connection string (URL that tells SQLAlchemy how to connect)
# Format: postgresql://username:password@host:port/database
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"Database URL: {DATABASE_URL}")

# Create the database engine
# This is the connection pool that handles talking to Postgres
engine = create_engine(
    DATABASE_URL,
    echo=False  # Set to True if you want to see SQL queries printed
)

# Create a session factory
# When you need to query the database, you call SessionLocal() to get a session
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)


def get_db():
    """
    Dependency function for FastAPI.
    
    When you have a FastAPI endpoint that needs database access, you do:
    
    @app.get("/complaints")
    def get_complaints(db: Session = Depends(get_db)):
        # Now db is a database session
        return db.query(Complaint).all()
    
    FastAPI automatically calls get_db() for you.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create all tables in the database.
    
    This is what you call once at the beginning to set up the schema.
    It reads all the models (Complaint, ComplaintFeature, ResolutionTarget)
    and creates the corresponding tables in Postgres.
    """
    from app.models.schema import Base
    
    print(f"Creating tables in {DATABASE_URL}...")
    Base.metadata.create_all(bind=engine)
    print("✓ All tables created successfully!")


if __name__ == "__main__":
    # If you run this file directly, it initializes the database
    init_db()