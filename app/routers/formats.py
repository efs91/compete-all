from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.post("/formats", response_model=schemas.Format)
def create_format(format: schemas.FormatCreate, db: Session = Depends(get_db)):
    db_format = models.Format(**format.dict())
    db.add(db_format)
    db.commit()
    db.refresh(db_format)
    return db_format

@router.get("/formats", response_model=List[schemas.Format])
def read_formats(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    formats = db.query(models.Format).offset(skip).limit(limit).all()
    return formats

@router.get("/formats/{format_id}", response_model=schemas.Format)
def read_format(format_id: str, db: Session = Depends(get_db)):
    db_format = db.query(models.Format).filter(models.Format.id == format_id).first()
    if db_format is None:
        raise HTTPException(status_code=404, detail="Format non trouvé")
    return db_format

@router.put("/formats/{format_id}", response_model=schemas.Format)
def update_format(format_id: str, format: schemas.FormatCreate, db: Session = Depends(get_db)):
    db_format = db.query(models.Format).filter(models.Format.id == format_id).first()
    if db_format is None:
        raise HTTPException(status_code=404, detail="Format non trouvé")
    
    for key, value in format.dict().items():
        setattr(db_format, key, value)
    
    db.commit()
    db.refresh(db_format)
    return db_format

@router.delete("/formats/{format_id}")
def delete_format(format_id: str, db: Session = Depends(get_db)):
    db_format = db.query(models.Format).filter(models.Format.id == format_id).first()
    if db_format is None:
        raise HTTPException(status_code=404, detail="Format non trouvé")
    
    db.delete(db_format)
    db.commit()
    return {"message": "Format supprimé"} 