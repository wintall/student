import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.models.user import User
db = SessionLocal()
for u in db.query(User).all():
    print(f'ID={u.id} username={u.username} phone={getattr(u, "phone", None)} email={getattr(u, "email", None)} status={getattr(u, "status", None)}')
db.close()
