import sqlite3

# Connexion à votre fichier de base de données
conn = sqlite3.connect('ecommerce.db')
cursor = conn.cursor()

print("🔄 Tentative d'ajout de la colonne 'stock'...")

try:
    # Commande SQL pour ajouter une colonne à une table existante
    cursor.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT 0")
    print("✅ Succès : La colonne 'stock' a été ajoutée à la table 'products'.")
except sqlite3.OperationalError as e:
    # Si l'erreur dit que la colonne existe déjà, ce n'est pas grave
    print(f"ℹ️ Information : {e}")

# Sauvegarde et fermeture
conn.commit()
conn.close()
print("🚀 Base de données mise à jour. Vous pouvez relancer le serveur.")