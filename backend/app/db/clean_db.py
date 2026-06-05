"""Database cleanup script: Recreates claims, documents, and decisions tables.
Leaves the members table completely untouched.
"""
import sys
from sqlalchemy import text
from app.db.database import engine
from app.db.models import Base


def clean():
    print("Connecting to database to clean up tables...")
    connection = engine.connect()
    transaction = connection.begin()
    try:
        print("Deleting data from decisions, documents, and claims...")
        connection.execute(text("DELETE FROM decisions;"))
        connection.execute(text("DELETE FROM documents;"))
        connection.execute(text("DELETE FROM claims;"))
        transaction.commit()
        print("Data deleted successfully.")
    except Exception as e:
        transaction.rollback()
        print(f"Error deleting data: {e}", file=sys.stderr)
        raise e
    finally:
        connection.close()


if __name__ == "__main__":
    clean()
