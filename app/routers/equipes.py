from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.post("/", response_model=schemas.Equipe)
def create_equipe(equipe: schemas.EquipeCreate, db: Session = Depends(get_db)):
    # Vérifier si tous les joueurs existent
    for joueur_id in equipe.membres:
        db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first()
        if db_joueur is None:
            raise HTTPException(status_code=404, detail=f"Joueur {joueur_id} non trouvé")
    
    db_equipe = models.Equipe(nom=equipe.nom)
    db_equipe.membres = [db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first() 
                        for joueur_id in equipe.membres]
    
    db.add(db_equipe)
    db.commit()
    db.refresh(db_equipe)
    return db_equipe

@router.get("/", response_model=List[schemas.Equipe])
def read_equipes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    equipes = db.query(models.Equipe).offset(skip).limit(limit).all()
    return equipes

@router.get("/{equipe_id}", response_model=schemas.Equipe)
def read_equipe(equipe_id: str, db: Session = Depends(get_db)):
    db_equipe = db.query(models.Equipe).filter(models.Equipe.id == equipe_id).first()
    if db_equipe is None:
        raise HTTPException(status_code=404, detail="Équipe non trouvée")
    return db_equipe

@router.put("/{equipe_id}", response_model=schemas.Equipe)
def update_equipe(equipe_id: str, equipe: schemas.EquipeCreate, db: Session = Depends(get_db)):
    db_equipe = db.query(models.Equipe).filter(models.Equipe.id == equipe_id).first()
    if db_equipe is None:
        raise HTTPException(status_code=404, detail="Équipe non trouvée")
    
    # Vérifier si tous les joueurs existent
    for joueur_id in equipe.membres:
        db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first()
        if db_joueur is None:
            raise HTTPException(status_code=404, detail=f"Joueur {joueur_id} non trouvé")
    
    db_equipe.nom = equipe.nom
    db_equipe.membres = [db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first() 
                        for joueur_id in equipe.membres]
    
    db.commit()
    db.refresh(db_equipe)
    return db_equipe

@router.delete("/{equipe_id}")
def delete_equipe(equipe_id: str, db: Session = Depends(get_db)):
    db_equipe = db.query(models.Equipe).filter(models.Equipe.id == equipe_id).first()
    if db_equipe is None:
        raise HTTPException(status_code=404, detail="Équipe non trouvée")
    
    db.delete(db_equipe)
    db.commit()
    return {"message": "Équipe supprimée"} 