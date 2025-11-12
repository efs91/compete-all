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

# Les commandes SQL à exécuter
sql_commands = [
    # Suppression des contraintes de clé étrangère
    "ALTER TABLE phase_joueur DROP FOREIGN KEY phase_joueur_ibfk_2",
    "ALTER TABLE equipe_joueur DROP FOREIGN KEY equipe_joueur_ibfk_2",
    "ALTER TABLE points_classement DROP FOREIGN KEY points_classement_ibfk_2",

    # Suppression de la table joueurs
    "DROP TABLE IF EXISTS joueurs",

    # Création de la nouvelle table joueurs
    """
    CREATE TABLE joueurs (
        id VARCHAR(36) PRIMARY KEY,
        username VARCHAR(255) NOT NULL UNIQUE,
        prenom VARCHAR(255),
        nom VARCHAR(255),
        email VARCHAR(255),
        date_naissance DATETIME,
        telephone VARCHAR(20),
        users_ingame JSON,
        user_discord VARCHAR(255),
        classements JSON,
        nation VARCHAR(255),
        club VARCHAR(255),
        status VARCHAR(255),
        comment VARCHAR(1000)
    )
    """,

    # Recréation des contraintes de clé étrangère
    """
    ALTER TABLE phase_joueur 
    ADD CONSTRAINT phase_joueur_ibfk_2 
    FOREIGN KEY (joueur_id) REFERENCES joueurs(id)
    """,

    """
    ALTER TABLE equipe_joueur 
    ADD CONSTRAINT equipe_joueur_ibfk_2 
    FOREIGN KEY (joueur_id) REFERENCES joueurs(id)
    """,

    """
    ALTER TABLE points_classement 
    ADD CONSTRAINT points_classement_ibfk_2 
    FOREIGN KEY (joueur_id) REFERENCES joueurs(id)
    """
]

# Exécution des commandes
for command in sql_commands:
    try:
        print(f"Exécution de la commande : {command[:60]}...")
        cursor.execute(command)
        print("✓ Succès")
    except Exception as e:
        print(f"❌ Erreur : {str(e)}")

# Valider les changements
db.commit()

# Vérifier la structure de la table
print("\nStructure de la nouvelle table joueurs :")
cursor.execute("DESCRIBE joueurs")
for row in cursor.fetchall():
    print(row)

# Fermer la connexion
cursor.close()
db.close()
print("\nTerminé !") 