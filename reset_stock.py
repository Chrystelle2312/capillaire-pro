from database import SessionLocal
from models import Product

db = SessionLocal()
products = db.query(Product).all()

print("🔄 Mise à jour des stocks à 50...")
for product in products:
    product.stock = 50

db.commit()
db.close()
print("✅ Terminé ! Tous les produits ont maintenant 50 unités en stock.")