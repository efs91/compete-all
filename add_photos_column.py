import os
from dotenv import load_dotenv
import mysql.connector

# Charger les variables d'environnement
load_dotenv()

# Connexion à la base de données
db = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    port=int(os.getenv('DB_PORT', 3306))
)

cursor = db.cursor()

try:
    # Ajout de la colonne photos
    cursor.execute("ALTER TABLE joueurs ADD COLUMN photos JSON;")
    print("✓ Colonne 'photos' ajoutée avec succès")
    
    # Vérifier la structure de la table
    cursor.execute("DESCRIBE joueurs")
    print("\nStructure de la table joueurs :")
    for row in cursor.fetchall():
        print(row)

    # Valider les changements
    db.commit()

except Exception as e:
    print(f"❌ Erreur : {str(e)}")
    db.rollback()

finally:
    # Fermer la connexion
    cursor.close()
    db.close()
    print("\nTerminé !") 