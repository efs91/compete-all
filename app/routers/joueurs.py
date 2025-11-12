from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from typing import List
from .. import models, schemas
from ..database import get_db
import logging
import sys
import uuid
import os
import shutil
from datetime import datetime

# Configuration des logs
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration du dossier static
PHOTOS_DIR = os.path.join("app", "static", "joueurs")
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

def get_joueur_photos_dir(joueur_id: str) -> str:
    """Crée et retourne le chemin du dossier des photos d'un joueur"""
    photos_dir = os.path.join(PHOTOS_DIR, joueur_id)
    if not os.path.exists(photos_dir):
        os.makedirs(photos_dir)
    return photos_dir

@router.post("/", response_model=schemas.JoueurSimple)
def create_joueur(joueur: schemas.JoueurCreate, db: Session = Depends(get_db)):
    logger.debug(f"Création d'un nouveau joueur avec les données: {joueur.dict()}")
    try:
        # Vérifier si le username existe déjà
        if db.query(models.Joueur).filter(models.Joueur.username == joueur.username).first():
            raise HTTPException(status_code=400, detail="Ce username est déjà utilisé")

        # Créer le joueur avec un nouvel ID
        db_joueur = models.Joueur(id=str(uuid.uuid4()), **joueur.dict())
        db.add(db_joueur)
        db.commit()
        db.refresh(db_joueur)
        logger.debug(f"Joueur créé avec succès, ID: {db_joueur.id}")
        return db_joueur
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la création du joueur: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[schemas.JoueurSimple])
def read_joueurs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.debug(f"Lecture de la liste des joueurs (skip={skip}, limit={limit})")
    try:
        # Log de la requête SQL
        query = db.query(models.Joueur).offset(skip).limit(limit)
        logger.debug(f"Requête SQL: {query}")
        
        # Exécution de la requête
        joueurs = query.all()
        logger.debug(f"Nombre de joueurs trouvés: {len(joueurs)}")
        
        # Log des données de chaque joueur
        for joueur in joueurs:
            logger.debug(f"Joueur trouvé: ID={joueur.id}, Username={joueur.username}")
            if hasattr(joueur, 'phases'):
                logger.debug(f"Phases pour joueur {joueur.id}: {[p.id for p in joueur.phases]}")
        
        return joueurs
    except Exception as e:
        logger.error(f"Erreur lors de la lecture des joueurs: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{joueur_id}", response_model=schemas.JoueurDetail)
def read_joueur(joueur_id: str, db: Session = Depends(get_db)):
    logger.debug(f"Recherche du joueur avec ID: {joueur_id}")
    try:
        # Construction de la requête avec joinedload
        query = db.query(models.Joueur).options(
            joinedload(models.Joueur.phases)
        ).filter(models.Joueur.id == joueur_id)
        logger.debug(f"Requête SQL: {query}")
        
        # Exécution de la requête
        db_joueur = query.first()
        
        if db_joueur is None:
            logger.warning(f"Joueur non trouvé avec ID: {joueur_id}")
            raise HTTPException(status_code=404, detail="Joueur non trouvé")
        
        # Log des détails du joueur
        logger.debug(f"Joueur trouvé: {db_joueur.username}")
        logger.debug(f"Phases associées: {[p.id for p in db_joueur.phases]}")
        
        return db_joueur
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du joueur: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{joueur_id}", response_model=schemas.JoueurDetail)
def update_joueur(joueur_id: str, joueur: schemas.JoueurCreate, db: Session = Depends(get_db)):
    logger.debug(f"Mise à jour du joueur {joueur_id} avec données: {joueur.dict()}")
    try:
        db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first()
        if db_joueur is None:
            logger.warning(f"Joueur non trouvé pour mise à jour: {joueur_id}")
            raise HTTPException(status_code=404, detail="Joueur non trouvé")
        
        # Vérifier si le nouveau username existe déjà (sauf si c'est le même joueur)
        if joueur.username != db_joueur.username:
            existing_username = db.query(models.Joueur).filter(
                models.Joueur.username == joueur.username,
                models.Joueur.id != joueur_id
            ).first()
            if existing_username:
                raise HTTPException(status_code=400, detail="Ce username est déjà utilisé")
        
        # Log avant modification
        logger.debug(f"Données actuelles: {vars(db_joueur)}")
        
        # Mise à jour de tous les champs
        for key, value in joueur.dict().items():
            setattr(db_joueur, key, value)
            logger.debug(f"Mise à jour de {key} = {value}")
        
        db.commit()
        db.refresh(db_joueur)
        logger.debug(f"Mise à jour réussie pour le joueur {joueur_id}")
        return db_joueur
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du joueur: {str(e)}")
        logger.exception("Traceback complet:")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{joueur_id}")
def delete_joueur(joueur_id: str, db: Session = Depends(get_db)):
    logger.debug(f"Suppression du joueur: {joueur_id}")
    try:
        db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first()
        if db_joueur is None:
            logger.warning(f"Joueur non trouvé pour suppression: {joueur_id}")
            raise HTTPException(status_code=404, detail="Joueur non trouvé")
        
        # Supprimer le dossier des photos du joueur s'il existe
        photos_dir = get_joueur_photos_dir(joueur_id)
        if os.path.exists(photos_dir):
            shutil.rmtree(photos_dir)
            logger.debug(f"Dossier des photos supprimé : {photos_dir}")
        
        db.delete(db_joueur)
        db.commit()
        logger.debug(f"Joueur {joueur_id} supprimé avec succès")
        return {"message": "Joueur supprimé"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du joueur: {str(e)}")
        logger.exception("Traceback complet:")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{joueur_id}/photos", response_model=schemas.JoueurDetail)
async def upload_photos(
    joueur_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    logger.debug(f"Upload de photos pour le joueur {joueur_id}")
    try:
        # Vérifier si le joueur existe
        db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first()
        if db_joueur is None:
            raise HTTPException(status_code=404, detail="Joueur non trouvé")

        # Créer une copie de la liste existante
        photo_urls = db_joueur.photos.copy() if db_joueur.photos else []
        logger.debug(f"Photos existantes: {photo_urls}")
        
        photos_dir = get_joueur_photos_dir(joueur_id)

        # Traiter chaque fichier
        for file in files:
            # Vérifier le type de fichier
            if not file.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail=f"Le fichier {file.filename} n'est pas une image")

            # Générer un nom de fichier unique basé sur un timestamp
            ext = os.path.splitext(file.filename)[1].lower()
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
            filepath = os.path.join(photos_dir, filename)

            # Sauvegarder le fichier
            try:
                with open(filepath, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                logger.debug(f"Photo sauvegardée : {filepath}")
                
                # Ajouter l'URL à la liste (chemin relatif au dossier static)
                photo_url = f"/static/joueurs/{joueur_id}/{filename}"
                photo_urls.append(photo_url)
                logger.debug(f"URL ajoutée: {photo_url}")
            
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde du fichier : {str(e)}")
                raise HTTPException(status_code=500, detail="Erreur lors de la sauvegarde du fichier")
            finally:
                file.file.close()

        # Mettre à jour la liste des photos dans la base de données
        logger.debug(f"Liste finale des photos: {photo_urls}")
        db_joueur.photos = photo_urls
        db.commit()
        db.refresh(db_joueur)
        logger.debug(f"Photos après refresh DB: {db_joueur.photos}")
        
        logger.debug(f"Photos ajoutées avec succès pour le joueur {joueur_id}")
        return db_joueur

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'upload des photos : {str(e)}")
        logger.exception("Traceback complet:")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{joueur_id}/photos/{photo_index}", response_model=schemas.JoueurDetail)
async def delete_photo(
    joueur_id: str,
    photo_index: int,
    db: Session = Depends(get_db)
):
    logger.debug(f"Suppression de la photo {photo_index} du joueur {joueur_id}")
    try:
        # Vérifier si le joueur existe
        db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first()
        if db_joueur is None:
            raise HTTPException(status_code=404, detail="Joueur non trouvé")

        # Vérifier si le joueur a des photos
        if not db_joueur.photos or photo_index >= len(db_joueur.photos):
            raise HTTPException(status_code=404, detail="Photo non trouvée")

        # Récupérer l'URL de la photo
        photo_url = db_joueur.photos[photo_index]
        logger.debug(f"Photo à supprimer: {photo_url}")
        
        # Supprimer le fichier physique
        filename = os.path.basename(photo_url)
        photos_dir = get_joueur_photos_dir(joueur_id)
        filepath = os.path.join(photos_dir, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.debug(f"Fichier physique supprimé : {filepath}")

            # Si le dossier est vide, le supprimer
            if not os.listdir(photos_dir):
                os.rmdir(photos_dir)
                logger.debug(f"Dossier vide supprimé : {photos_dir}")

        # Créer une nouvelle liste sans la photo à supprimer
        photos_list = db_joueur.photos.copy() if db_joueur.photos else []
        if 0 <= photo_index < len(photos_list):
            logger.debug(f"Avant suppression: {photos_list}")
            photos_list.pop(photo_index)
            logger.debug(f"Après suppression: {photos_list}")
            
            # Mettre à jour la liste des photos dans la base de données
            db_joueur.photos = photos_list
            db.commit()
            db.refresh(db_joueur)
            logger.debug(f"Photos après refresh DB: {db_joueur.photos}")
        else:
            logger.warning(f"Index de photo invalide: {photo_index}, longueur: {len(photos_list)}")
        
        logger.debug(f"Photo supprimée avec succès pour le joueur {joueur_id}")
        return db_joueur

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la photo : {str(e)}")
        logger.exception("Traceback complet:")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{joueur_id}/photos", response_model=schemas.JoueurDetail)
async def delete_all_photos(
    joueur_id: str,
    db: Session = Depends(get_db)
):
    logger.debug(f"Suppression de toutes les photos du joueur {joueur_id}")
    try:
        # Vérifier si le joueur existe
        db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first()
        if db_joueur is None:
            raise HTTPException(status_code=404, detail="Joueur non trouvé")

        # Supprimer le dossier des photos s'il existe
        photos_dir = get_joueur_photos_dir(joueur_id)
        if os.path.exists(photos_dir):
            shutil.rmtree(photos_dir)
            logger.debug(f"Dossier des photos supprimé : {photos_dir}")
            os.makedirs(photos_dir)  # Recréer le dossier vide

        # Vider la liste des photos dans la base de données
        logger.debug(f"Photos avant suppression: {db_joueur.photos}")
        db_joueur.photos = []
        db.commit()
        db.refresh(db_joueur)
        logger.debug(f"Photos après refresh DB: {db_joueur.photos}")
        
        logger.debug(f"Toutes les photos supprimées avec succès pour le joueur {joueur_id}")
        return db_joueur

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des photos : {str(e)}")
        logger.exception("Traceback complet:")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) 