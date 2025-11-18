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
                    
                    # Récupérer la liste actuelle ou créer une nouvelle avec 2 places
                    participants_actuels = match_suivant.participants if match_suivant.participants else []
                    
                    # Créer une nouvelle liste avec exactement 2 places
                    nouveaux_participants = [None, None]
                    
                    # Copier les participants existants
                    for i, p in enumerate(participants_actuels):
                        if i < 2:
                            nouveaux_participants[i] = p
                    
                    # Placer le gagnant à la bonne position
                    nouveaux_participants[position_dans_match_suivant] = gagnant.participant_id
                    
                    # Assigner la nouvelle liste (IMPORTANT: créer une nouvelle liste pour que SQLAlchemy détecte le changement)
                    match_suivant.participants = nouveaux_participants
                    
                    # Marquer explicitement comme modifié pour SQLAlchemy
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(match_suivant, 'participants')
                    
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

@router.put("/rencontres/{rencontre_id}/resultats/bulk")
def update_rencontre_resultats_bulk(
    rencontre_id: str, 
    resultats: List[schemas.ResultatCreate], 
    db: Session = Depends(get_db)
):
    """Mettre à jour tous les résultats d'une rencontre en une seule requête (optimisé)"""
    
    # Vérifier que la rencontre existe
    db_rencontre = db.query(models.Rencontre).filter(models.Rencontre.id == rencontre_id).first()
    if not db_rencontre:
        raise HTTPException(status_code=404, detail="Rencontre non trouvée")
    
    # Supprimer tous les résultats existants de cette rencontre
    db.query(models.Resultat).filter(models.Resultat.rencontre_id == rencontre_id).delete()
    
    # Créer les nouveaux résultats
    nouveaux_resultats = []
    for resultat_data in resultats:
        # Vérifier que le participant existe
        participant = db.query(models.Joueur).filter(models.Joueur.id == resultat_data.participant_id).first()
        if not participant:
            raise HTTPException(status_code=404, detail=f"Joueur {resultat_data.participant_id} non trouvé")
        
        db_resultat = models.Resultat(**resultat_data.dict())
        db_resultat.rencontre_id = rencontre_id
        db.add(db_resultat)
        nouveaux_resultats.append(db_resultat)
    
    # Gérer la propagation du gagnant pour les tableaux d'élimination AVANT le commit
    phase = db.query(models.Phase).filter(models.Phase.id == db_rencontre.phase_id).first()
    if phase and phase.type_general in ['elimination', 'tableau'] and db_rencontre.tour:
        # Trouver le gagnant (classement = 1)
        gagnant_data = next((r for r in resultats if r.classement == 1), None)
        
        if gagnant_data:
            # Calculer la position du match suivant
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
                position_dans_match_suivant = db_rencontre.position % 2
                
                # Mettre à jour les participants
                participants_actuels = match_suivant.participants if match_suivant.participants else []
                nouveaux_participants = [None, None]
                
                for i, p in enumerate(participants_actuels):
                    if i < 2:
                        nouveaux_participants[i] = p
                
                nouveaux_participants[position_dans_match_suivant] = gagnant_data.participant_id
                match_suivant.participants = nouveaux_participants
                
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(match_suivant, 'participants')
                db.add(match_suivant)
    
    # Un seul commit pour tout
    db.commit()
    
    # Rafraîchir pour obtenir les IDs
    for r in nouveaux_resultats:
        db.refresh(r)
    
    return {"success": True, "message": "Résultats mis à jour"} 