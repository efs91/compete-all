from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db
import json

router = APIRouter()

@router.post("/upload", response_model=schemas.Classement)
async def upload_classement(
    file: UploadFile = File(...),
    evenement_id: str = None,
    phase_id: str = None,
    rencontre_id: str = None,
    db: Session = Depends(get_db)
):
    # Vérifier qu'au moins un ID est fourni
    if not any([evenement_id, phase_id, rencontre_id]):
        raise HTTPException(status_code=400, detail="Il faut spécifier au moins un événement, une phase ou une rencontre")
    
    # Vérifier que l'entité existe
    if evenement_id:
        if not db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first():
            raise HTTPException(status_code=404, detail="Événement non trouvé")
    if phase_id:
        if not db.query(models.Phase).filter(models.Phase.id == phase_id).first():
            raise HTTPException(status_code=404, detail="Phase non trouvée")
    if rencontre_id:
        if not db.query(models.Rencontre).filter(models.Rencontre.id == rencontre_id).first():
            raise HTTPException(status_code=404, detail="Rencontre non trouvée")

    # Lire et valider le JSON
    try:
        content = await file.read()
        data = json.loads(content)
        if not isinstance(data, dict) or 'nom' not in data or 'points' not in data:
            raise HTTPException(status_code=400, detail="Format JSON invalide")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON invalide")

    # Créer le classement
    db_classement = models.Classement(
        nom=data['nom'],
        evenement_id=evenement_id,
        phase_id=phase_id,
        rencontre_id=rencontre_id
    )
    db.add(db_classement)
    
    # Ajouter les points
    for i, point in enumerate(data['points'], 1):
        if not db.query(models.Joueur).filter(models.Joueur.id == point['joueur_id']).first():
            continue  # Ignorer les joueurs qui n'existent pas
        
        db_point = models.PointsClassement(
            classement_id=db_classement.id,
            joueur_id=point['joueur_id'],
            points=point['points'],
            rang=point.get('rang', i)  # Utiliser le rang fourni ou la position dans la liste
        )
        db.add(db_point)

    db.commit()
    db.refresh(db_classement)
    return db_classement

@router.get("/evenements/{evenement_id}/classements", response_model=List[schemas.Classement])
def read_classements_evenement(evenement_id: str, db: Session = Depends(get_db)):
    return db.query(models.Classement).filter(models.Classement.evenement_id == evenement_id).all()

@router.get("/phases/{phase_id}/classements", response_model=List[schemas.Classement])
def read_classements_phase(phase_id: str, db: Session = Depends(get_db)):
    return db.query(models.Classement).filter(models.Classement.phase_id == phase_id).all()

@router.get("/rencontres/{rencontre_id}/classements", response_model=List[schemas.Classement])
def read_classements_rencontre(rencontre_id: str, db: Session = Depends(get_db)):
    return db.query(models.Classement).filter(models.Classement.rencontre_id == rencontre_id).all()

@router.get("/{classement_id}", response_model=schemas.Classement)
def read_classement(classement_id: str, db: Session = Depends(get_db)):
    db_classement = db.query(models.Classement).filter(models.Classement.id == classement_id).first()
    if not db_classement:
        raise HTTPException(status_code=404, detail="Classement non trouvé")
    return db_classement

@router.put("/{classement_id}", response_model=schemas.Classement)
def update_classement(classement_id: str, classement: schemas.ClassementCreate, db: Session = Depends(get_db)):
    db_classement = db.query(models.Classement).filter(models.Classement.id == classement_id).first()
    if not db_classement:
        raise HTTPException(status_code=404, detail="Classement non trouvé")
    
    # Mettre à jour les informations de base
    for key, value in classement.dict(exclude={'points'}).items():
        setattr(db_classement, key, value)
    
    # Supprimer les anciens points
    db.query(models.PointsClassement).filter(models.PointsClassement.classement_id == classement_id).delete()
    
    # Ajouter les nouveaux points
    for point in classement.points:
        if not db.query(models.Joueur).filter(models.Joueur.id == point.joueur_id).first():
            continue  # Ignorer les joueurs qui n'existent pas
        
        db_point = models.PointsClassement(**point.dict(), classement_id=classement_id)
        db.add(db_point)
    
    db.commit()
    db.refresh(db_classement)
    return db_classement

@router.delete("/{classement_id}")
def delete_classement(classement_id: str, db: Session = Depends(get_db)):
    db_classement = db.query(models.Classement).filter(models.Classement.id == classement_id).first()
    if not db_classement:
        raise HTTPException(status_code=404, detail="Classement non trouvé")
    
    db.delete(db_classement)
    db.commit()
    return {"message": "Classement supprimé"} 