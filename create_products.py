from database import SessionLocal, Base, engine
from models import Product

# Crée la table si elle n'existe pas
Base.metadata.create_all(bind=engine)

db = SessionLocal()

products_data = [
    {"name": "Shampoing Lisse & Doux", "price": 12.99, "image": "shampoo.jpg", "message": "Pour un lissage parfait et cheveux doux."},
    {"name": "Après-shampoing Hydratant", "price": 14.99, "image": "conditioner.jpg", "message": "Hydrate et démêle vos cheveux."},
    {"name": "Sérum Anti-casse", "price": 19.99, "image": "serum.jpg", "message": "Répare les cheveux fragiles et cassants."},
    {"name": "Crème Défrisante Douce", "price": 15.99, "image": "cream.jpg", "message": "Lissage parfait sans agression."},
    {"name": "Masque Réparateur", "price": 18.50, "image": "mask.jpg", "message": "Restaure la vitalité des cheveux abîmés."},
    {"name": "Huile Nourrissante", "price": 16.75, "image": "oil.jpg", "message": "Pour des cheveux brillants et nourris."},
    {"name": "Spray Brillance", "price": 13.50, "image": "spray.jpg", "message": "Apporte éclat et douceur immédiate."},
    {"name": "Gel Fixation Légère", "price": 11.99, "image": "gel.jpg", "message": "Fixe sans alourdir vos cheveux."}
]

for p in products_data:
    product = Product(name=p["name"], price=p["price"], image=p["image"], message=p["message"])
    db.add(product)

db.commit()
db.close()
print("✅ Produits insérés dans SQLite !")