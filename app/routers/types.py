from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.post("/types", response_model=schemas.Type)
def create_type(type: schemas.TypeCreate, db: Session = Depends(get_db)):
    db_type = models.Type(**type.dict())
    db.add(db_type)
    db.commit()
    db.refresh(db_type)
    return db_type

@router.get("/types", response_model=List[schemas.Type])
def read_types(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    types = db.query(models.Type).offset(skip).limit(limit).all()
    return types

@router.get("/types/{type_id}", response_model=schemas.Type)
def read_type(type_id: str, db: Session = Depends(get_db)):
    db_type = db.query(models.Type).filter(models.Type.id == type_id).first()
    if db_type is None:
        raise HTTPException(status_code=404, detail="Type non trouvé")
    return db_type

@router.put("/types/{type_id}", response_model=schemas.Type)
def update_type(type_id: str, type: schemas.TypeCreate, db: Session = Depends(get_db)):
    db_type = db.query(models.Type).filter(models.Type.id == type_id).first()
    if db_type is None:
        raise HTTPException(status_code=404, detail="Type non trouvé")
    
    for key, value in type.dict().items():
        setattr(db_type, key, value)
    
    db.commit()
    db.refresh(db_type)
    return db_type

@router.delete("/types/{type_id}")
def delete_type(type_id: str, db: Session = Depends(get_db)):
    db_type = db.query(models.Type).filter(models.Type.id == type_id).first()
    if db_type is None:
        raise HTTPException(status_code=404, detail="Type non trouvé")
    
    db.delete(db_type)
    db.commit()
    return {"message": "Type supprimé"} 