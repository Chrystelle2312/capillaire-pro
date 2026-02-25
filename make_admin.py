import sys
from database import SessionLocal
from models import User

def make_user_admin(username: str):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()

    if not user:
        print(f"❌ Erreur : L'utilisateur '{username}' n'a pas été trouvé.")
        db.close()
        return

    user.is_admin = True
    db.commit()
    print(f"✅ Succès ! L'utilisateur '{username}' est maintenant un administrateur.")
    db.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python make_admin.py <username>")
    else:
        username_to_admin = sys.argv[1]
        make_user_admin(username_to_admin)