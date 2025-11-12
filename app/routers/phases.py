from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict
from .. import models, schemas
from ..database import get_db
from sqlalchemy import select, func, text
import logging

router = APIRouter()

# Fonction utilitaire pour formater une phase avec ses joueurs pour un événement spécifique
def format_phase_response(db_phase: models.Phase, evenement_id: str, db: Session) -> Dict:
    # Récupérer les associations phase_evenement_joueur
    associations = db.query(models.phase_evenement_joueur).filter(
        models.phase_evenement_joueur.c.phase_id == db_phase.id,
        models.phase_evenement_joueur.c.evenement_id == evenement_id
    ).all()
    
    # Formater les joueurs selon le schéma attendu
    formatted_joueurs = []
    for assoc in associations:
        # Récupérer le joueur correspondant
        joueur = db.query(models.Joueur).filter(models.Joueur.id == assoc.joueur_id).first()
        if joueur:
            # Créer un objet PhaseEvenementJoueurDetail
            joueur_detail = schemas.PhaseEvenementJoueurDetail(
                phase_id=db_phase.id,
                evenement_id=evenement_id,
                joueur_id=joueur.id,
                ordre_inscription=assoc.ordre_inscription,
                seed=assoc.seed,
                joueur=joueur
            )
            formatted_joueurs.append(joueur_detail)
    
    # Créer une copie du dictionnaire de la phase
    phase_dict = {
        'id': db_phase.id,
        'nom': db_phase.nom,
        'format_id': db_phase.format_id,
        'type_id': db_phase.type_id,
        'scoring': db_phase.scoring,
        'configuration': db_phase.configuration,
        'format': db_phase.format,
        'type': db_phase.type,
        'joueurs': formatted_joueurs
    }
    
    return phase_dict

# =========== ROUTES POUR LES PHASES (TEMPLATES) ===========

@router.post("/phases", response_model=schemas.PhaseSimple)
def create_phase_template(phase: schemas.PhaseCreate, db: Session = Depends(get_db)):
    """Crée un nouveau template de phase sans l'associer à un événement"""
    db_phase = models.Phase(**phase.dict())
    db.add(db_phase)
    db.commit()
    db.refresh(db_phase)
    return db_phase

@router.get("/phases", response_model=List[schemas.PhaseSimple])
def read_all_phase_templates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Liste tous les templates de phases disponibles"""
    phases = db.query(models.Phase).offset(skip).limit(limit).all()
    return phases

@router.get("/phases/{phase_id}", response_model=schemas.PhaseSimple)
def read_phase_template(phase_id: str, db: Session = Depends(get_db)):
    """Récupère un template de phase par son ID"""
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if db_phase is None:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    return db_phase

@router.put("/phases/{phase_id}", response_model=schemas.PhaseSimple)
def update_phase_template(phase_id: str, phase: schemas.PhaseCreate, db: Session = Depends(get_db)):
    """Met à jour un template de phase"""
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if db_phase is None:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    for key, value in phase.dict().items():
        setattr(db_phase, key, value)
    
    db.commit()
    db.refresh(db_phase)
    return db_phase

@router.delete("/phases/{phase_id}")
def delete_phase_template(phase_id: str, db: Session = Depends(get_db)):
    """Supprime un template de phase"""
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if db_phase is None:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    # Vérifier si la phase est utilisée dans des événements
    phase_events = db.query(models.phase_evenement).filter(
        models.phase_evenement.c.phase_id == phase_id
    ).count()
    
    if phase_events > 0:
        raise HTTPException(
            status_code=400, 
            detail="Cette phase est utilisée dans un ou plusieurs événements et ne peut pas être supprimée"
        )
    
    # Supprimer les références dans phase_joueur s'il y en a
    try:
        # Utiliser une requête SQL directe car la table phase_joueur n'est plus dans le modèle SQLAlchemy
        db.execute(
            text("DELETE FROM phase_joueur WHERE phase_id = :phase_id"),
            {"phase_id": phase_id}
        )
        print(f"Suppression des références dans phase_joueur pour la phase {phase_id}")
    except Exception as e:
        print(f"Erreur lors de la suppression des références dans phase_joueur: {e}")
        # Continuer même en cas d'erreur car la table pourrait ne plus exister
    
    # Supprimer la phase
    db.delete(db_phase)
    db.commit()
    return {"message": "Phase supprimée"}

# =========== ROUTES POUR LES PHASES DANS LES ÉVÉNEMENTS ===========

@router.post("/evenements/{evenement_id}/phases", response_model=schemas.PhaseInEvent)
def add_phase_to_event(
    evenement_id: str, 
    phase_relation: schemas.PhaseEventRelation, 
    db: Session = Depends(get_db)
):
    """Ajoute une phase existante à un événement avec la liste des joueurs"""
    # Vérifier si l'événement existe
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Vérifier si la phase existe
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_relation.phase_id).first()
    if db_phase is None:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    # Vérifier si la phase est déjà dans l'événement
    existing = db.query(models.phase_evenement).filter(
        models.phase_evenement.c.phase_id == phase_relation.phase_id,
        models.phase_evenement.c.evenement_id == evenement_id
    ).first()
    
    if not existing:
        # Ajouter la relation phase-événement
        stmt = models.phase_evenement.insert().values(
            phase_id=phase_relation.phase_id,
            evenement_id=evenement_id
        )
        db.execute(stmt)
    
    # Ajouter les joueurs s'ils sont spécifiés
    if phase_relation.joueurs:
        for i, joueur_data in enumerate(phase_relation.joueurs, 1):
            # Vérifier si le joueur existe
            db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_data.joueur_id).first()
            if db_joueur is None:
                continue
            
            # Vérifier si l'association existe déjà
            existing_joueur = db.query(models.phase_evenement_joueur).filter(
                models.phase_evenement_joueur.c.phase_id == phase_relation.phase_id,
                models.phase_evenement_joueur.c.evenement_id == evenement_id,
                models.phase_evenement_joueur.c.joueur_id == joueur_data.joueur_id
            ).first()
            
            if existing_joueur:
                continue
            
            # Ajouter l'association avec l'ordre d'inscription et le seed
            stmt = models.phase_evenement_joueur.insert().values(
                phase_id=phase_relation.phase_id,
                evenement_id=evenement_id,
                joueur_id=joueur_data.joueur_id,
                ordre_inscription=joueur_data.ordre_inscription,
                seed=joueur_data.seed
            )
            db.execute(stmt)
    
    db.commit()
    return format_phase_response(db_phase, evenement_id, db)

@router.get("/evenements/{evenement_id}/phases", response_model=List[schemas.PhaseInEvent])
def read_phases_for_event(evenement_id: str, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Liste toutes les phases d'un événement avec leurs joueurs"""
    # Vérifier si l'événement existe
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Récupérer les IDs des phases associées à cet événement
    phase_ids = db.query(models.phase_evenement.c.phase_id).filter(
        models.phase_evenement.c.evenement_id == evenement_id
    ).all()
    
    phase_ids = [p[0] for p in phase_ids]
    
    # Récupérer les phases
    phases = db.query(models.Phase).filter(models.Phase.id.in_(phase_ids)).offset(skip).limit(limit).all()
    
    return [format_phase_response(phase, evenement_id, db) for phase in phases]

@router.get("/evenements/{evenement_id}/phases/{phase_id}", response_model=schemas.PhaseInEvent)
def read_phase_in_event(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Récupère les détails d'une phase spécifique dans un événement"""
    # Vérifier si la phase existe
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if db_phase is None:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    # Vérifier si la phase est dans l'événement
    phase_in_event = db.query(models.phase_evenement).filter(
        models.phase_evenement.c.phase_id == phase_id,
        models.phase_evenement.c.evenement_id == evenement_id
    ).first()
    
    if not phase_in_event:
        raise HTTPException(status_code=404, detail="Phase non trouvée dans cet événement")
    
    return format_phase_response(db_phase, evenement_id, db)

@router.delete("/evenements/{evenement_id}/phases/{phase_id}")
def remove_phase_from_event(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Retire une phase d'un événement"""
    # Vérifier si la relation existe
    phase_in_event = db.query(models.phase_evenement).filter(
        models.phase_evenement.c.phase_id == phase_id,
        models.phase_evenement.c.evenement_id == evenement_id
    ).first()
    
    if not phase_in_event:
        raise HTTPException(status_code=404, detail="Phase non trouvée dans cet événement")
    
    # Supprimer les relations joueurs-phase-événement
    db.execute(
        models.phase_evenement_joueur.delete().where(
            models.phase_evenement_joueur.c.phase_id == phase_id,
            models.phase_evenement_joueur.c.evenement_id == evenement_id
        )
    )
    
    # Supprimer la relation phase-événement
    db.execute(
        models.phase_evenement.delete().where(
            models.phase_evenement.c.phase_id == phase_id,
            models.phase_evenement.c.evenement_id == evenement_id
        )
    )
    
    db.commit()
    return {"message": "Phase retirée de l'événement"}

# =========== ROUTES POUR LES JOUEURS DANS LES PHASES D'UN ÉVÉNEMENT ===========

@router.post("/evenements/{evenement_id}/phases/{phase_id}/joueurs", response_model=schemas.PhaseInEvent)
def add_joueurs_to_phase_in_event(
    evenement_id: str,
    phase_id: str,
    joueurs: List[schemas.PhaseEvenementJoueurCreate],
    db: Session = Depends(get_db)
):
    """Ajoute des joueurs à une phase spécifique d'un événement"""
    # Vérifier si la phase est dans l'événement
    phase_in_event = db.query(models.phase_evenement).filter(
        models.phase_evenement.c.phase_id == phase_id,
        models.phase_evenement.c.evenement_id == evenement_id
    ).first()
    
    if not phase_in_event:
        raise HTTPException(status_code=404, detail="Phase non trouvée dans cet événement")
    
    # Récupérer le dernier ordre d'inscription
    max_ordre = db.execute(
        select(func.max(models.phase_evenement_joueur.c.ordre_inscription)).where(
            models.phase_evenement_joueur.c.phase_id == phase_id,
            models.phase_evenement_joueur.c.evenement_id == evenement_id
        )
    ).scalar() or 0
    
    # Ajouter les nouveaux joueurs
    for i, joueur_data in enumerate(joueurs, max_ordre + 1):
        # Vérifier si le joueur existe
        db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_data.joueur_id).first()
        if db_joueur is None:
            continue
        
        # Vérifier si le joueur n'est pas déjà dans la phase
        existing = db.execute(
            select(models.phase_evenement_joueur).where(
                models.phase_evenement_joueur.c.phase_id == phase_id,
                models.phase_evenement_joueur.c.evenement_id == evenement_id,
                models.phase_evenement_joueur.c.joueur_id == joueur_data.joueur_id
            )
        ).first()
        if existing:
            continue
        
        # Ajouter l'association
        stmt = models.phase_evenement_joueur.insert().values(
            phase_id=phase_id,
            evenement_id=evenement_id,
            joueur_id=joueur_data.joueur_id,
            ordre_inscription=i,
            seed=joueur_data.seed
        )
        db.execute(stmt)
    
    db.commit()

    # Récupérer la phase mise à jour
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    
    return format_phase_response(db_phase, evenement_id, db)

@router.get("/evenements/{evenement_id}/phases/{phase_id}/joueurs", response_model=List[schemas.PhaseEvenementJoueurDetail])
def get_joueurs_phase_in_event(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Récupère la liste des joueurs d'une phase dans un événement"""
    # Vérifier si la phase est dans l'événement
    phase_in_event = db.query(models.phase_evenement).filter(
        models.phase_evenement.c.phase_id == phase_id,
        models.phase_evenement.c.evenement_id == evenement_id
    ).first()
    
    if not phase_in_event:
        raise HTTPException(status_code=404, detail="Phase non trouvée dans cet événement")
    
    # Récupérer les associations phase_evenement_joueur
    associations = db.query(models.phase_evenement_joueur).filter(
        models.phase_evenement_joueur.c.phase_id == phase_id,
        models.phase_evenement_joueur.c.evenement_id == evenement_id
    ).all()
    
    # Formater les joueurs selon le schéma attendu
    result = []
    for assoc in associations:
        # Récupérer le joueur correspondant
        joueur = db.query(models.Joueur).filter(models.Joueur.id == assoc.joueur_id).first()
        if joueur:
            # Créer un objet PhaseEvenementJoueurDetail
            joueur_detail = schemas.PhaseEvenementJoueurDetail(
            phase_id=phase_id,
                evenement_id=evenement_id,
            joueur_id=joueur.id,
            ordre_inscription=assoc.ordre_inscription,
            seed=assoc.seed,
            joueur=joueur
            )
            result.append(joueur_detail)
    
    return result

@router.delete("/evenements/{evenement_id}/phases/{phase_id}/joueurs/{joueur_id}")
def remove_joueur_from_phase_in_event(evenement_id: str, phase_id: str, joueur_id: str, db: Session = Depends(get_db)):
    """Retire un joueur d'une phase spécifique d'un événement"""
    # Supprimer l'association
    result = db.execute(
        models.phase_evenement_joueur.delete().where(
            models.phase_evenement_joueur.c.phase_id == phase_id,
            models.phase_evenement_joueur.c.evenement_id == evenement_id,
            models.phase_evenement_joueur.c.joueur_id == joueur_id
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Joueur non trouvé dans cette phase de cet événement")
    
    db.commit()
    return {"message": "Joueur retiré de la phase"}