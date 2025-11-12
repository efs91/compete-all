from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.post("/", response_model=schemas.Participant)
def create_participant(participant: schemas.ParticipantCreate, db: Session = Depends(get_db)):
    db_participant = models.Participant(**participant.dict())
    db.add(db_participant)
    db.commit()
    db.refresh(db_participant)
    return db_participant

@router.get("/", response_model=List[schemas.Participant])
def read_participants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    participants = db.query(models.Participant).offset(skip).limit(limit).all()
    return participants

@router.get("/{participant_id}", response_model=schemas.Participant)
def read_participant(participant_id: str, db: Session = Depends(get_db)):
    db_participant = db.query(models.Participant).filter(models.Participant.id == participant_id).first()
    if db_participant is None:
        raise HTTPException(status_code=404, detail="Participant non trouvé")
    return db_participant

@router.put("/{participant_id}", response_model=schemas.Participant)
def update_participant(participant_id: str, participant: schemas.ParticipantCreate, db: Session = Depends(get_db)):
    db_participant = db.query(models.Participant).filter(models.Participant.id == participant_id).first()
    if db_participant is None:
        raise HTTPException(status_code=404, detail="Participant non trouvé")
    
    for key, value in participant.dict().items():
        setattr(db_participant, key, value)
    
    db.commit()
    db.refresh(db_participant)
    return db_participant

@router.delete("/{participant_id}")
def delete_participant(participant_id: str, db: Session = Depends(get_db)):
    db_participant = db.query(models.Participant).filter(models.Participant.id == participant_id).first()
    if db_participant is None:
        raise HTTPException(status_code=404, detail="Participant non trouvé")
    
    db.delete(db_participant)
    db.commit()
    return {"message": "Participant supprimé"} 