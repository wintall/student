"""
Fill missing emails for internal users so the email composer can search and select them.

The generated addresses are internal demo addresses under `student.local`. Existing
email addresses are kept unchanged.

Run:
    python -m scripts.sync_user_emails
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, engine
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User


DOMAIN = "student.local"


def normalize(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def email_for_user(user: User) -> str:
    if user.student:
        return f"{normalize(user.student.student_no)}@{DOMAIN}"
    if user.teacher:
        return f"{normalize(user.teacher.employee_no)}@{DOMAIN}"
    return f"{normalize(user.username)}@{DOMAIN}"


def main():
    engine.echo = False
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_deleted == False).all()
        used = {
            row[0].lower()
            for row in db.query(User.email).filter(User.email != None, User.email != "").all()
            if row[0]
        }
        updated = 0

        for user in users:
            if user.email:
                continue

            email = email_for_user(user)
            base, domain = email.split("@", 1)
            candidate = email
            suffix = 2
            while candidate.lower() in used:
                candidate = f"{base}{suffix}@{domain}"
                suffix += 1

            user.email = candidate
            used.add(candidate.lower())
            updated += 1

        db.commit()
        print(f"User emails synchronized. Updated: {updated}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
