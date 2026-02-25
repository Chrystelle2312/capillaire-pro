import os
import urllib.request

# Chemin du dossier actuel
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")
images_dir = os.path.join(static_dir, "images")

# Liste des images définies dans create_products.py
image_names = [
    "shampoing.webp",
    "conditioner.webp",
    "serum.webp",
    "creme.webp",
    "masque.webp",
    "huile.webp",
    "spray.webp",
    "gel.webp",
    
]

# 1. Création des dossiers
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    print(f"📂 Dossier créé : {static_dir}")

if not os.path.exists(images_dir):
    os.makedirs(images_dir)
    print(f"📂 Dossier créé : {images_dir}")
print(f"📍 Vos images doivent être ici : {images_dir}")

# 2. Téléchargement d'images de test (placeholders)
print("⬇️ Téléchargement des images de démonstration...")

for img_name in image_names:
    img_path = os.path.join(images_dir, img_name)
    
    # On ne télécharge que si l'image n'existe pas déjà
    if not os.path.exists(img_path):
        # Création d'une URL pour une image générique avec le nom du produit
        text = img_name.replace(".jpg", "").capitalize()
        # Utilisation de placehold.co (service gratuit d'images)
        url = f"https://placehold.co/300x300/e91e63/ffffff.jpg?text={text}"
        
        try:
            urllib.request.urlretrieve(url, img_path)
            print(f"✅ Image générée : {img_name}")
        except Exception as e:
            print(f"❌ Erreur pour {img_name} : {e}")
    else:
        print(f"ℹ️ Image déjà présente : {img_name}")

print("\n✨ Terminé ! Les dossiers sont créés et les images sont prêtes.")