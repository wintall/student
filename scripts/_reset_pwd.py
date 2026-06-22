import sys
sys.path.insert(0, '.')
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User
db = SessionLocal()
# 更新 student40 的密码
h = hash_password('123456')
u = db.query(User).filter(User.username == 'student40').first()
print(f'old hash:', h)
u.password_hash = h
db.commit()
print('student40 密码已重置为 123456')
db.close()
