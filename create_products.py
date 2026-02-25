from database import SessionLocal, Base, engine
from models import Product

# Crée la table si elle n'existe pas
Base.metadata.create_all(bind=engine)

db = SessionLocal()

products_data = [
    {"name": "Shampoing Lisse & Doux", "price": 12.99, "image": "shampoing.webp", "message": "Pour un lissage parfait et cheveux doux."},
    {"name": "Après-shampoing Hydratant", "price": 14.99, "image": "conditioner.webp", "message": "Hydrate et démêle vos cheveux."},
    {"name": "Sérum Anti-casse", "price": 19.99, "image": "serum.webp", "message": "Répare les cheveux fragiles et cassants."},
    {"name": "Crème Défrisante Douce", "price": 15.99, "image": "creme.webp", "message": "Lissage parfait sans agression."},
    {"name": "Masque Réparateur", "price": 18.50, "image": "masque.webp", "message": "Restaure la vitalité des cheveux abîmés."},
    {"name": "Huile Nourrissante", "price": 16.75, "image": "huile.webp", "message": "Pour des cheveux brillants et nourris."},
    {"name": "Spray Brillance", "price": 13.50, "image": "spray.webp", "message": "Apporte éclat et douceur immédiate."},
    {"name": "Gel Fixation Légère", "price": 11.99, "image": "gel.webp", "message": "Fixe sans alourdir vos cheveux."}
]

for p in products_data:
    # Vérifie si le produit existe déjà pour éviter les doublons
    existing_product = db.query(Product).filter(Product.name == p["name"]).first()
    if not existing_product:
        product = Product(name=p["name"], price=p["price"], image=p["image"], message=p["message"], stock=50)
        db.add(product)
        print(f"Ajouté : {p['name']}")
    else:
        # Met à jour l'image et le prix même si le produit existe déjà
        existing_product.image = p["image"]
        existing_product.price = p["price"]
        print(f"Mis à jour : {p['name']}")

db.commit()
db.close()
print("✅ Initialisation des produits terminée !")