from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.post("/", response_model=schemas.Regle)
def create_regle(regle: schemas.RegleCreate, db: Session = Depends(get_db)):
    # Vérifier si une règle existe déjà pour ce sport
    db_regle = db.query(models.Regle).filter(models.Regle.sport == regle.sport).first()
    if db_regle:
        raise HTTPException(status_code=400, detail="Une règle existe déjà pour ce sport")
    
    db_regle = models.Regle(**regle.dict())
    db.add(db_regle)
    db.commit()
    db.refresh(db_regle)
    return db_regle

@router.get("/", response_model=List[schemas.Regle])
def read_regles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    regles = db.query(models.Regle).offset(skip).limit(limit).all()
    return regles

@router.get("/{sport}", response_model=schemas.Regle)
def read_regle(sport: str, db: Session = Depends(get_db)):
    db_regle = db.query(models.Regle).filter(models.Regle.sport == sport).first()
    if db_regle is None:
        raise HTTPException(status_code=404, detail="Règle non trouvée")
    return db_regle

@router.put("/{sport}", response_model=schemas.Regle)
def update_regle(sport: str, regle: schemas.RegleCreate, db: Session = Depends(get_db)):
    db_regle = db.query(models.Regle).filter(models.Regle.sport == sport).first()
    if db_regle is None:
        raise HTTPException(status_code=404, detail="Règle non trouvée")
    
    for key, value in regle.dict().items():
        setattr(db_regle, key, value)
    
    db.commit()
    db.refresh(db_regle)
    return db_regle

@router.delete("/{sport}")
def delete_regle(sport: str, db: Session = Depends(get_db)):
    db_regle = db.query(models.Regle).filter(models.Regle.sport == sport).first()
    if db_regle is None:
        raise HTTPException(status_code=404, detail="Règle non trouvée")
    
    db.delete(db_regle)
    db.commit()
    return {"message": "Règle supprimée"} 