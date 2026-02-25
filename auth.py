from passlib.context import CryptContext

# Utilisation de pbkdf2_sha256 qui est plus stable et ne nécessite pas d'outils de compilation complexe
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """Vérifie un mot de passe en clair par rapport à sa version hachée."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Hache un mot de passe."""
    return pwd_context.hash(password)