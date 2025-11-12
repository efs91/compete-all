from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.post("/phases/{phase_id}/rencontres", response_model=schemas.Rencontre)
def create_rencontre(phase_id: str, rencontre: schemas.RencontreCreate, db: Session = Depends(get_db)):
    # Vérifier si la phase existe
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if db_phase is None:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    db_rencontre = models.Rencontre(**rencontre.dict())
    db_rencontre.phase_id = phase_id
    db.add(db_rencontre)
    db.commit()
    db.refresh(db_rencontre)
    return db_rencontre

@router.get("/phases/{phase_id}/rencontres", response_model=List[schemas.Rencontre])
def read_rencontres(phase_id: str, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    rencontres = db.query(models.Rencontre).filter(models.Rencontre.phase_id == phase_id).offset(skip).limit(limit).all()
    return rencontres

@router.get("/rencontres/{rencontre_id}", response_model=schemas.Rencontre)
def read_rencontre(rencontre_id: str, db: Session = Depends(get_db)):
    db_rencontre = db.query(models.Rencontre).filter(models.Rencontre.id == rencontre_id).first()
    if db_rencontre is None:
        raise HTTPException(status_code=404, detail="Rencontre non trouvée")
    return db_rencontre

@router.put("/rencontres/{rencontre_id}", response_model=schemas.Rencontre)
def update_rencontre(rencontre_id: str, rencontre: schemas.RencontreCreate, db: Session = Depends(get_db)):
    db_rencontre = db.query(models.Rencontre).filter(models.Rencontre.id == rencontre_id).first()
    if db_rencontre is None:
        raise HTTPException(status_code=404, detail="Rencontre non trouvée")
    
    for key, value in rencontre.dict().items():
        setattr(db_rencontre, key, value)
    
    db.commit()
    db.refresh(db_rencontre)
    return db_rencontre

@router.delete("/rencontres/{rencontre_id}")
def delete_rencontre(rencontre_id: str, db: Session = Depends(get_db)):
    db_rencontre = db.query(models.Rencontre).filter(models.Rencontre.id == rencontre_id).first()
    if db_rencontre is None:
        raise HTTPException(status_code=404, detail="Rencontre non trouvée")
    
    db.delete(db_rencontre)
    db.commit()
    return {"message": "Rencontre supprimée"} 