from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from .. import models, schemas
from ..database import get_db

router = APIRouter()

# Modèle pour la saisie rapide depuis la feuille de poule
class ResultatQuickSave(BaseModel):
    joueur_id: str
    adversaire_id: str
    value: str  # "V" ou un nombre
    max_points: int = 15

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

@router.get("/phases/{phase_id}/rencontres-complete", response_model=List[Dict[str, Any]])
def read_rencontres_complete(phase_id: str, db: Session = Depends(get_db)):
    """
    Récupère toutes les rencontres d'une phase avec leurs résultats et participants en une seule requête optimisée.
    Évite le problème N+1 queries.
    """
    # Vérifier si la phase existe
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if db_phase is None:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    # Récupérer toutes les rencontres de la phase
    rencontres = db.query(models.Rencontre).filter(models.Rencontre.phase_id == phase_id).all()
    
    # Récupérer tous les IDs de participants uniques
    all_participant_ids = set()
    for rencontre in rencontres:
        if rencontre.participants:
            all_participant_ids.update(rencontre.participants)
    
    # Récupérer tous les joueurs en une seule requête
    joueurs = db.query(models.Joueur).filter(models.Joueur.id.in_(all_participant_ids)).all()
    joueurs_dict = {joueur.id: joueur for joueur in joueurs}
    
    # Récupérer tous les résultats en une seule requête
    rencontre_ids = [r.id for r in rencontres]
    resultats = db.query(models.Resultat).filter(models.Resultat.rencontre_id.in_(rencontre_ids)).all()
    
    # Organiser les résultats par rencontre
    resultats_by_rencontre = {}
    for resultat in resultats:
        if resultat.rencontre_id not in resultats_by_rencontre:
            resultats_by_rencontre[resultat.rencontre_id] = []
        resultats_by_rencontre[resultat.rencontre_id].append({
            "id": resultat.id,
            "participant_id": resultat.participant_id,
            "classement": resultat.classement,
            "points": resultat.points,
            "actions": resultat.actions
        })
    
    # Construire la réponse complète
    result = []
    for rencontre in rencontres:
        # Déterminer le statut : "Terminée" si des résultats existent, sinon "En attente"
        has_resultats = rencontre.id in resultats_by_rencontre and len(resultats_by_rencontre[rencontre.id]) > 0
        
        rencontre_data = {
            "id": rencontre.id,
            "phase_id": rencontre.phase_id,
            "evenement_id": rencontre.evenement_id,
            "participants": rencontre.participants,
            "poule_id": rencontre.poule_id,
            "statut": "Terminée" if has_resultats else "En attente",
            "participants_details": [],
            "resultats": resultats_by_rencontre.get(rencontre.id, [])
        }
        
        # Ajouter les détails des participants
        if rencontre.participants:
            for participant_id in rencontre.participants:
                joueur = joueurs_dict.get(participant_id)
                if joueur:
                    rencontre_data["participants_details"].append({
                        "id": joueur.id,
                        "username": joueur.username,
                        "prenom": joueur.prenom,
                        "nom": joueur.nom,
                        "club": joueur.club
                    })
                else:
                    rencontre_data["participants_details"].append({
                        "id": participant_id,
                        "username": "Inconnu",
                        "club": ""
                    })
        
        result.append(rencontre_data)
    
    return result

@router.post("/phases/{phase_id}/feuille-poule/save-result")
def save_feuille_poule_result(
    phase_id: str,
    data: ResultatQuickSave,
    db: Session = Depends(get_db)
):
    """
    Sauvegarde rapide d'un résultat depuis la feuille de poule.
    Crée ou trouve la rencontre entre les deux joueurs, puis crée/met à jour les résultats.
    Accepte 'V' (victoire), 'D' (défaite), ou un score numérique.
    """
    # Vérifier si la phase existe
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if db_phase is None:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    # Récupérer l'evenement_id de la phase via la table de liaison
    from sqlalchemy import select
    stmt = select(models.phase_evenement.c.evenement_id).where(
        models.phase_evenement.c.phase_id == phase_id
    )
    result = db.execute(stmt).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Phase non associée à un événement")
    
    evenement_id = result[0]
    
    # Chercher une rencontre existante entre ces deux joueurs dans cette phase
    rencontres = db.query(models.Rencontre).filter(
        models.Rencontre.phase_id == phase_id
    ).all()
    
    rencontre = None
    for r in rencontres:
        if (r.participants and 
            data.joueur_id in r.participants and 
            data.adversaire_id in r.participants):
            rencontre = r
            break
    
    # Si la rencontre n'existe pas, la créer
    if rencontre is None:
        rencontre = models.Rencontre(
            phase_id=phase_id,
            evenement_id=evenement_id,
            participants=[data.joueur_id, data.adversaire_id]
        )
        db.add(rencontre)
        db.commit()
        db.refresh(rencontre)
    
    # Interpréter la valeur saisie pour ce joueur uniquement
    value_upper = data.value.strip().upper()
    
    if value_upper == 'V':
        # Victoire au maximum de points
        joueur_points = data.max_points
    elif value_upper == 'D':
        # Défaite (pas utilisé normalement, mais on met 0)
        joueur_points = 0
    else:
        # Score numérique
        try:
            joueur_points = int(value_upper)
            if joueur_points < 0:
                raise HTTPException(status_code=400, detail="Le score ne peut pas être négatif")
            if joueur_points > data.max_points:
                raise HTTPException(status_code=400, detail=f"Le score ne peut pas dépasser {data.max_points}")
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur invalide. Utilisez 'V' ou un nombre.")
    
    # Créer ou mettre à jour le résultat du joueur
    resultat_joueur = db.query(models.Resultat).filter(
        models.Resultat.rencontre_id == rencontre.id,
        models.Resultat.participant_id == data.joueur_id
    ).first()
    
    if resultat_joueur:
        resultat_joueur.points = joueur_points
    else:
        resultat_joueur = models.Resultat(
            rencontre_id=rencontre.id,
            participant_id=data.joueur_id,
            points=joueur_points
        )
        db.add(resultat_joueur)
    
    # Récupérer le résultat de l'adversaire s'il existe
    resultat_adversaire = db.query(models.Resultat).filter(
        models.Resultat.rencontre_id == rencontre.id,
        models.Resultat.participant_id == data.adversaire_id
    ).first()
    
    adversaire_points = resultat_adversaire.points if resultat_adversaire else None
    
    # Si les deux résultats existent, calculer les classements
    if adversaire_points is not None:
        if joueur_points > adversaire_points:
            resultat_joueur.classement = 1
            resultat_adversaire.classement = 2
        elif adversaire_points > joueur_points:
            resultat_joueur.classement = 2
            resultat_adversaire.classement = 1
        else:
            # Égalité (ne devrait pas arriver avec validation frontend)
            resultat_joueur.classement = 1
            resultat_adversaire.classement = 1
    else:
        # Adversaire pas encore saisi, pas de classement
        resultat_joueur.classement = None
    
    db.commit()
    db.refresh(resultat_joueur)
    if resultat_adversaire:
        db.refresh(resultat_adversaire)
    
    return {
        "success": True,
        "rencontre_id": rencontre.id,
        "joueur": {
            "id": data.joueur_id,
            "points": joueur_points,
            "classement": resultat_joueur.classement
        },
        "adversaire": {
            "id": data.adversaire_id,
            "points": adversaire_points,
            "classement": resultat_adversaire.classement if resultat_adversaire else None
        }
    }