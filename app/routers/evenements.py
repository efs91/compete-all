from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.post("/", response_model=schemas.Evenement)
def create_evenement(evenement: schemas.EvenementCreate, db: Session = Depends(get_db)):
    db_evenement = models.Evenement(**evenement.dict())
    db.add(db_evenement)
    db.commit()
    db.refresh(db_evenement)
    return db_evenement

@router.get("/", response_model=List[schemas.Evenement])
def read_evenements(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    evenements = db.query(models.Evenement).offset(skip).limit(limit).all()
    return evenements

@router.get("/{evenement_id}", response_model=schemas.Evenement)
def read_evenement(evenement_id: str, db: Session = Depends(get_db)):
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    return db_evenement

@router.put("/{evenement_id}", response_model=schemas.Evenement)
def update_evenement(evenement_id: str, evenement: schemas.EvenementCreate, db: Session = Depends(get_db)):
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    for key, value in evenement.dict().items():
        setattr(db_evenement, key, value)
    
    db.commit()
    db.refresh(db_evenement)
    return db_evenement

@router.delete("/{evenement_id}")
def delete_evenement(evenement_id: str, db: Session = Depends(get_db)):
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    db.delete(db_evenement)
    db.commit()
    return {"message": "Événement supprimé"} 