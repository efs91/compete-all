from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from . import models

load_dotenv()

SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_and_update_schema():
    """Vérification et mise à jour du schéma de la base de données."""
    # Créer une connexion
    with engine.connect() as connection:
        try:
            # Vérifier si la colonne evenement_id existe dans la table rencontres
            result = connection.execute(text("SHOW COLUMNS FROM rencontres LIKE 'evenement_id'"))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Migration: Ajout de la colonne evenement_id à la table rencontres")
                # Ajouter la colonne evenement_id à la table rencontres sans contrainte
                try:
                    connection.execute(text("ALTER TABLE rencontres ADD COLUMN evenement_id VARCHAR(36)"))
                    connection.commit()
                    print("Colonne evenement_id ajoutée à la table rencontres")
                except SQLAlchemyError as e:
                    print(f"Erreur lors de l'ajout de la colonne evenement_id: {e}")
                    connection.rollback()
            
            # Vérifier si la colonne regle_id existe dans la table classements
            result = connection.execute(text("SHOW COLUMNS FROM classements LIKE 'regle_id'"))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Migration: Ajout de la colonne regle_id à la table classements")
                # Ajouter la colonne regle_id à la table classements sans contrainte
                try:
                    connection.execute(text("ALTER TABLE classements ADD COLUMN regle_id VARCHAR(36)"))
                    connection.commit()
                    print("Colonne regle_id ajoutée à la table classements")
                except SQLAlchemyError as e:
                    print(f"Erreur lors de l'ajout de la colonne regle_id: {e}")
                    connection.rollback()
            
            # Vérifier si la colonne points existe dans la table classements
            result = connection.execute(text("SHOW COLUMNS FROM classements LIKE 'points'"))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Migration: Ajout de la colonne points à la table classements")
                # Ajouter la colonne points à la table classements
                try:
                    connection.execute(text("ALTER TABLE classements ADD COLUMN points JSON"))
                    connection.commit()
                    print("Colonne points ajoutée à la table classements")
                except SQLAlchemyError as e:
                    print(f"Erreur lors de l'ajout de la colonne points: {e}")
                    connection.rollback()
            
            # Vérifier si la colonne participants existe dans la table rencontres
            result = connection.execute(text("SHOW COLUMNS FROM rencontres LIKE 'participants'"))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Migration: Ajout de la colonne participants à la table rencontres")
                try:
                    connection.execute(text("ALTER TABLE rencontres ADD COLUMN participants JSON"))
                    connection.commit()
                    print("Colonne participants ajoutée à la table rencontres")
                except SQLAlchemyError as e:
                    print(f"Erreur lors de l'ajout de la colonne participants: {e}")
                    connection.rollback()
            
            # Vérifier si la colonne resultats_config existe dans la table types
            result = connection.execute(text("SHOW COLUMNS FROM types LIKE 'resultats_config'"))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Migration: Ajout de la colonne resultats_config à la table types")
                try:
                    connection.execute(text("ALTER TABLE types ADD COLUMN resultats_config JSON"))
                    connection.commit()
                    print("Colonne resultats_config ajoutée à la table types")
                except SQLAlchemyError as e:
                    print(f"Erreur lors de l'ajout de la colonne resultats_config: {e}")
                    connection.rollback()
            
            # Rendre les colonnes classement et points nullables dans resultats
            result = connection.execute(text("SHOW COLUMNS FROM resultats LIKE 'classement'"))
            column_info = result.fetchone()
            
            if column_info and 'NO' in str(column_info):
                print("Migration: Rendre classement et points nullables dans resultats")
                try:
                    connection.execute(text("ALTER TABLE resultats MODIFY COLUMN classement INT NULL"))
                    connection.execute(text("ALTER TABLE resultats MODIFY COLUMN points INT NULL"))
                    connection.commit()
                    print("Colonnes classement et points rendues nullables")
                except SQLAlchemyError as e:
                    print(f"Erreur lors de la modification des colonnes: {e}")
                    connection.rollback()
            
            # Ajouter les colonnes type_general, ordre et description à la table phases
            for col_name, col_type in [('type_general', 'VARCHAR(50)'), ('ordre', 'INT'), ('description', 'VARCHAR(1000)')]:
                result = connection.execute(text(f"SHOW COLUMNS FROM phases LIKE '{col_name}'"))
                column_exists = result.fetchone() is not None
                
                if not column_exists:
                    print(f"Migration: Ajout de la colonne {col_name} à la table phases")
                    try:
                        connection.execute(text(f"ALTER TABLE phases ADD COLUMN {col_name} {col_type}"))
                        connection.commit()
                        print(f"Colonne {col_name} ajoutée à la table phases")
                    except SQLAlchemyError as e:
                        print(f"Erreur lors de l'ajout de la colonne {col_name}: {e}")
                        connection.rollback()
                
        except SQLAlchemyError as e:
            print(f"Erreur lors de la vérification/mise à jour du schéma: {e}")
            connection.rollback()
            raise 