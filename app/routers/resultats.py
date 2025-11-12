from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.post("/rencontres/{rencontre_id}/resultats", response_model=schemas.Resultat)
def create_resultat(rencontre_id: str, resultat: schemas.ResultatCreate, db: Session = Depends(get_db)):
    # Vérifier si la rencontre existe
    db_rencontre = db.query(models.Rencontre).filter(models.Rencontre.id == rencontre_id).first()
    if db_rencontre is None:
        raise HTTPException(status_code=404, detail="Rencontre non trouvée")
    
    # Vérifier si le participant (joueur ou équipe) existe
    participant = db.query(models.Joueur).filter(models.Joueur.id == resultat.participant_id).first()
    if participant is None:
        raise HTTPException(status_code=404, detail="Joueur non trouvé")
    
    # Vérifier si un résultat existe déjà pour ce participant dans cette rencontre
    existing_resultat = db.query(models.Resultat).filter(
        models.Resultat.rencontre_id == rencontre_id,
        models.Resultat.participant_id == resultat.participant_id
    ).first()
    if existing_resultat:
        raise HTTPException(status_code=400, detail="Un résultat existe déjà pour ce participant dans cette rencontre")
    
    db_resultat = models.Resultat(**resultat.dict())
    db_resultat.rencontre_id = rencontre_id
    db.add(db_resultat)
    db.commit()
    db.refresh(db_resultat)
    return db_resultat

@router.get("/rencontres/{rencontre_id}/resultats", response_model=List[schemas.Resultat])
def read_resultats(rencontre_id: str, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    resultats = db.query(models.Resultat).filter(models.Resultat.rencontre_id == rencontre_id).offset(skip).limit(limit).all()
    return resultats

@router.get("/resultats/{resultat_id}", response_model=schemas.Resultat)
def read_resultat(resultat_id: str, db: Session = Depends(get_db)):
    db_resultat = db.query(models.Resultat).filter(models.Resultat.id == resultat_id).first()
    if db_resultat is None:
        raise HTTPException(status_code=404, detail="Résultat non trouvé")
    return db_resultat

@router.put("/resultats/{resultat_id}", response_model=schemas.Resultat)
def update_resultat(resultat_id: str, resultat: schemas.ResultatCreate, db: Session = Depends(get_db)):
    db_resultat = db.query(models.Resultat).filter(models.Resultat.id == resultat_id).first()
    if db_resultat is None:
        raise HTTPException(status_code=404, detail="Résultat non trouvé")
    
    # Vérifier si le participant (joueur) existe
    participant = db.query(models.Joueur).filter(models.Joueur.id == resultat.participant_id).first()
    if participant is None:
        raise HTTPException(status_code=404, detail="Joueur non trouvé")
    
    for key, value in resultat.dict().items():
        setattr(db_resultat, key, value)
    
    db.commit()
    db.refresh(db_resultat)
    return db_resultat

@router.delete("/resultats/{resultat_id}")
def delete_resultat(resultat_id: str, db: Session = Depends(get_db)):
    db_resultat = db.query(models.Resultat).filter(models.Resultat.id == resultat_id).first()
    if db_resultat is None:
        raise HTTPException(status_code=404, detail="Résultat non trouvé")
    
    db.delete(db_resultat)
    db.commit()
    return {"message": "Résultat supprimé"} 