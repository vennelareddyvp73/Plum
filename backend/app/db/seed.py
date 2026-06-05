"""Seed test members matching test_cases.json"""
from datetime import date
from sqlalchemy import text
from app.db.database import engine, SessionLocal
from app.db.models import Base, Member


def seed():
    # Run database migration to add gender and age columns if not already present
    connection = engine.connect()
    try:
        connection.execute(text("ALTER TABLE members ADD COLUMN IF NOT EXISTS gender VARCHAR;"))
        connection.execute(text("ALTER TABLE members ADD COLUMN IF NOT EXISTS age INTEGER;"))
        connection.commit()
        print("Ensured gender and age columns exist in members table.")
    except Exception as e:
        print(f"[migration] ALTER TABLE failed: {e}")
    finally:
        connection.close()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    members = [
        Member(id="EMP001", name="Rajesh Kumar",    age=35, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP002", name="Priya Singh",     age=30, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP003", name="Amit Verma",      age=40, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP004", name="Sneha Reddy",     age=28, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP005", name="Vikram Joshi",    age=45, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,9,1)),
        Member(id="EMP006", name="Kavita Nair",     age=38, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP007", name="Suresh Patil",    age=50, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP008", name="Ravi Menon",      age=35, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP009", name="Anita Desai",     age=42, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP010", name="Deepak Shah",     age=32, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP011", name="Amit Patel",      age=29, policy_start_date=date(2024,6,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,6,15)),
        Member(id="EMP012", name="Neha Gupta",      age=31, policy_start_date=date(2025,1,1),  policy_end_date=date(2026,12,31), is_active=True, join_date=date(2025,1,1)),
        Member(id="EMP013", name="Sanjay Sharma",   age=44, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,2,1)),
        Member(id="EMP014", name="Anjali Desai",    age=27, policy_start_date=date(2025,6,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2025,6,1)),
        Member(id="EMP015", name="Vijay Krishnan",  age=36, policy_start_date=date(2026,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2026,1,10)),
        Member(id="EMP016", name="Sunita Rao",      age=48, policy_start_date=date(2024,8,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,8,15)),
        Member(id="EMP017", name="Rahul Nair",      age=33, policy_start_date=date(2025,3,1),  policy_end_date=date(2026,12,31), is_active=True, join_date=date(2025,3,1)),
        Member(id="EMP018", name="Meera Joshi",     age=39, policy_start_date=date(2024,11,1), policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,11,1)),
        Member(id="EMP019", name="Alok Singh",      age=41, policy_start_date=date(2025,9,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2025,9,15)),
        Member(id="EMP020", name="Pooja Reddy",     age=26, policy_start_date=date(2026,2,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2026,2,1)),
        Member(id="EMP021", name="Rohan Mehta",     age=37, policy_start_date=date(2024,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,1,1)),
        Member(id="EMP022", name="Kiran Kapoor",    age=34, policy_start_date=date(2025,1,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2025,1,15)),
        Member(id="EMP023", name="Arjun Saxena",    age=43, policy_start_date=date(2024,5,1),  policy_end_date=date(2026,12,31), is_active=True, join_date=date(2024,5,1)),
        Member(id="EMP024", name="Shruti Sen",      age=25, policy_start_date=date(2025,4,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2025,4,1)),
        Member(id="EMP025", name="Aditya Mishra",   age=46, policy_start_date=date(2026,3,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2026,3,10)),
        Member(id="EMP026", name="Divya Pillai",    age=30, policy_start_date=date(2024,10,1), policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,10,1)),
        Member(id="EMP027", name="Sandeep Chaudhary",age=52, policy_start_date=date(2025,10,1),policy_end_date=date(2026,12,31), is_active=True, join_date=date(2025,10,1)),
        Member(id="EMP028", name="Nisha Hegde",     age=35, policy_start_date=date(2024,3,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2024,3,1)),
        Member(id="EMP029", name="Manish Prasad",   age=47, policy_start_date=date(2025,8,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2025,8,15)),
        Member(id="EMP030", name="Aishwarya Iyer",  age=28, policy_start_date=date(2026,4,1),  policy_end_date=date(2027,12,31), is_active=True, join_date=date(2026,4,1)),
    ]

    female_names = {
        "Priya", "Sneha", "Kavita", "Anita", "Neha", "Anjali", "Sunita", 
        "Meera", "Pooja", "Kiran", "Shruti", "Divya", "Nisha", "Aishwarya"
    }

    for m in members:
        first_name = m.name.split()[0]
        m.gender = "Female" if first_name in female_names else "Male"

        existing = db.query(Member).filter(Member.id == m.id).first()
        if not existing:
            db.add(m)
        else:
            existing.gender = m.gender
            existing.age = m.age

    db.commit()
    db.close()
    print("Seeded members with gender and age.")


if __name__ == "__main__":
    seed()