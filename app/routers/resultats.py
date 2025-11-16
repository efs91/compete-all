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
    
    # Si c'est un tableau d'élimination, mettre à jour le match du tour suivant avec le gagnant
    phase = db.query(models.Phase).filter(models.Phase.id == db_rencontre.phase_id).first()
    if phase and phase.type_general in ['elimination', 'tableau'] and db_rencontre.tour:
        # Vérifier si ce match est terminé (tous les résultats saisis)
        tous_resultats = db.query(models.Resultat).filter(
            models.Resultat.rencontre_id == rencontre_id
        ).all()
        
        if len(tous_resultats) == len(db_rencontre.participants):
            # Match terminé, trouver le gagnant (classement = 1)
            gagnant = next((r for r in tous_resultats if r.classement == 1), None)
            
            if gagnant:
                # Calculer la position du match suivant : position_suivante = position_actuelle // 2
                position_suivante = db_rencontre.position // 2
                tour_suivant = db_rencontre.tour + 1
                
                # Trouver le match du tour suivant
                match_suivant = db.query(models.Rencontre).filter(
                    models.Rencontre.phase_id == db_rencontre.phase_id,
                    models.Rencontre.tour == tour_suivant,
                    models.Rencontre.position == position_suivante
                ).first()
                
                if match_suivant:
                    # Déterminer la position dans le match suivant
                    # Match position paire (0, 2, 4...) → position 0 du match suivant
                    # Match position impaire (1, 3, 5...) → position 1 du match suivant
                    position_dans_match_suivant = db_rencontre.position % 2
                    
                    # Initialiser le tableau avec 2 places si vide
                    if not match_suivant.participants or len(match_suivant.participants) == 0:
                        match_suivant.participants = [None, None]
                    elif len(match_suivant.participants) == 1:
                        match_suivant.participants.append(None)
                    
                    # Placer le gagnant à la bonne position
                    match_suivant.participants[position_dans_match_suivant] = gagnant.participant_id
                    
                    # Nettoyer les None pour avoir une liste propre
                    match_suivant.participants = [p for p in match_suivant.participants if p is not None]
                    
                    db.add(match_suivant)
                    db.commit()
    
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