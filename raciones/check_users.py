from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    users = db.session.scalars(db.select(User)).all()
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"ID: {u.id}, Username: '{u.username}', Email: '{u.email}', Hash_len: {len(u.password_hash) if u.password_hash else 0}, Hash: {u.password_hash}")
