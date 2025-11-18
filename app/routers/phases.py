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
        'type_general': db_phase.type_general,  # AJOUT : type_general pour affichage mode tableau
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

@router.get("/phases/{phase_id}/debug-config")
def debug_phase_config(phase_id: str, db: Session = Depends(get_db)):
    """DEBUG - Affiche la configuration complète d'une phase"""
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if db_phase is None:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    config = db_phase.configuration or {}
    
    return {
        "phase_id": phase_id,
        "phase_nom": db_phase.nom,
        "configuration": config,
        "configuration_type": str(type(config)),
        "joueurs_min": config.get('joueurs_min', 'NON DEFINI'),
        "joueurs_max": config.get('joueurs_max', 'NON DEFINI'),
        "joueurs_souhaite": config.get('joueurs_souhaite', 'NON DEFINI'),
        "config_keys": list(config.keys()) if isinstance(config, dict) else "Not a dict"
    }

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
        # Déterminer le prochain ordre disponible
        max_ordre = db.execute(
            select(func.max(models.phase_evenement.c.ordre))
            .where(models.phase_evenement.c.evenement_id == evenement_id)
        ).scalar()
        
        next_ordre = (max_ordre or 0) + 1
        
        # Fusionner config_qualification et config_decalages dans un seul JSON
        config = phase_relation.config_qualification or {}
        if phase_relation.config_decalages:
            config['decalages'] = phase_relation.config_decalages
        
        # Ajouter la relation phase-événement avec l'ordre et la config complète
        stmt = models.phase_evenement.insert().values(
            phase_id=phase_relation.phase_id,
            evenement_id=evenement_id,
            ordre=next_ordre,
            config_qualification=config
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
    """Liste toutes les phases d'un événement avec leurs joueurs, triées par ordre"""
    # Vérifier si l'événement existe
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Récupérer les phases avec leur ordre
    phase_ordres = db.execute(
        select(models.phase_evenement.c.phase_id, models.phase_evenement.c.ordre)
        .where(models.phase_evenement.c.evenement_id == evenement_id)
        .order_by(models.phase_evenement.c.ordre)
    ).all()
    
    phase_ids = [p[0] for p in phase_ordres]
    
    if not phase_ids:
        return []
    
    # Récupérer les phases dans l'ordre
    phases = db.query(models.Phase).filter(models.Phase.id.in_(phase_ids)).all()
    
    # Créer un dictionnaire pour garder l'ordre
    phase_dict = {phase.id: phase for phase in phases}
    phases_ordered = [phase_dict[phase_id] for phase_id in phase_ids if phase_id in phase_dict]
    
    return [format_phase_response(phase, evenement_id, db) for phase in phases_ordered]

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

@router.post("/evenements/{evenement_id}/phases/{phase_id}/reinitialiser")
def reinitialiser_donnees_phase(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Supprime UNIQUEMENT les rencontres et résultats d'une phase (garde la phase et les joueurs inscrits)"""
    # Vérifier si la phase existe dans l'événement
    phase_in_event = db.query(models.phase_evenement).filter(
        models.phase_evenement.c.phase_id == phase_id,
        models.phase_evenement.c.evenement_id == evenement_id
    ).first()
    
    if not phase_in_event:
        raise HTTPException(status_code=404, detail="Phase non trouvée dans cet événement")
    
    # 1. Récupérer les IDs des rencontres
    rencontres = db.query(models.Rencontre).filter(
        models.Rencontre.phase_id == phase_id,
        models.Rencontre.evenement_id == evenement_id
    ).all()
    rencontre_ids = [r.id for r in rencontres]
    
    nb_rencontres = len(rencontres)
    
    if rencontre_ids:
        # 2. Supprimer les résultats
        nb_resultats = db.query(models.Resultat).filter(
            models.Resultat.rencontre_id.in_(rencontre_ids)
        ).delete(synchronize_session=False)
        
        # 3. Supprimer les rencontres
        db.query(models.Rencontre).filter(
            models.Rencontre.phase_id == phase_id,
            models.Rencontre.evenement_id == evenement_id
        ).delete(synchronize_session=False)
    
    # 4. Supprimer les poules (SANS supprimer les associations joueurs-poule)
    poules = db.query(models.Poule).filter(
        models.Poule.phase_id == phase_id,
        models.Poule.evenement_id == evenement_id
    ).all()
    
    for poule in poules:
        # Supprimer les associations joueurs-poule
        db.execute(
            models.poule_joueur.delete().where(
                models.poule_joueur.c.poule_id == poule.id
            )
        )
        # Supprimer la poule
        db.delete(poule)
    
    db.commit()
    
    return {
        "message": "Données de la phase réinitialisées avec succès",
        "rencontres_supprimees": nb_rencontres,
        "phase_id": phase_id,
        "note": "La phase et les joueurs inscrits sont conservés"
    }

@router.delete("/evenements/{evenement_id}/phases/{phase_id}")
def remove_phase_from_event(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Retire une phase d'un événement et supprime toutes les données associées (rencontres, résultats, classements)"""
    # Vérifier si la relation existe
    phase_in_event = db.query(models.phase_evenement).filter(
        models.phase_evenement.c.phase_id == phase_id,
        models.phase_evenement.c.evenement_id == evenement_id
    ).first()
    
    if not phase_in_event:
        raise HTTPException(status_code=404, detail="Phase non trouvée dans cet événement")
    
    # 1. Récupérer les IDs des rencontres de cette phase dans cet événement
    rencontres = db.query(models.Rencontre).filter(
        models.Rencontre.phase_id == phase_id,
        models.Rencontre.evenement_id == evenement_id
    ).all()
    rencontre_ids = [r.id for r in rencontres]
    
    if rencontre_ids:
        # 2. Supprimer les résultats liés à ces rencontres
        db.query(models.Resultat).filter(
            models.Resultat.rencontre_id.in_(rencontre_ids)
        ).delete(synchronize_session=False)
        
        # 3. Supprimer les classements liés à ces rencontres
        db.query(models.Classement).filter(
            models.Classement.rencontre_id.in_(rencontre_ids)
        ).delete(synchronize_session=False)
        
        # 4. Supprimer les rencontres
        db.query(models.Rencontre).filter(
            models.Rencontre.phase_id == phase_id,
            models.Rencontre.evenement_id == evenement_id
        ).delete(synchronize_session=False)
    
    # 5. Supprimer les classements liés à cette phase dans cet événement
    db.query(models.Classement).filter(
        models.Classement.phase_id == phase_id,
        models.Classement.evenement_id == evenement_id
    ).delete(synchronize_session=False)
    
    # 6. Supprimer les poules de cette phase
    poules = db.query(models.Poule).filter(
        models.Poule.phase_id == phase_id,
        models.Poule.evenement_id == evenement_id
    ).all()
    
    for poule in poules:
        # Supprimer les associations joueurs-poule
        db.execute(
            models.poule_joueur.delete().where(
                models.poule_joueur.c.poule_id == poule.id
            )
        )
        # Supprimer la poule
        db.delete(poule)
    
    # 7. Supprimer les relations joueurs-phase-événement
    db.execute(
        models.phase_evenement_joueur.delete().where(
            models.phase_evenement_joueur.c.phase_id == phase_id,
            models.phase_evenement_joueur.c.evenement_id == evenement_id
        )
    )
    
    # 8. Supprimer la relation phase-événement
    db.execute(
        models.phase_evenement.delete().where(
            models.phase_evenement.c.phase_id == phase_id,
            models.phase_evenement.c.evenement_id == evenement_id
        )
    )
    
    db.commit()
    return {"message": "Phase retirée de l'événement avec toutes ses données (poules incluses)"}

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

@router.get("/evenements/{evenement_id}/phases/{phase_id}/completion-status")
def check_phase_completion(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Vérifie si une phase est complètement terminée (toutes les rencontres ont des résultats)"""
    # Vérifier que la phase existe dans cet événement
    phase_event_rel = db.execute(
        models.phase_evenement.select().where(
            models.phase_evenement.c.phase_id == phase_id,
            models.phase_evenement.c.evenement_id == evenement_id
        )
    ).first()
    
    if not phase_event_rel:
        raise HTTPException(status_code=404, detail="Phase non trouvée dans cet événement")
    
    # Récupérer toutes les rencontres de cette phase dans cet événement
    rencontres = db.query(models.Rencontre).filter(
        models.Rencontre.phase_id == phase_id,
        models.Rencontre.evenement_id == evenement_id
    ).all()
    
    if not rencontres:
        return {
            "complete": False,
            "message": "Aucune rencontre créée pour cette phase",
            "total_rencontres": 0,
            "rencontres_terminees": 0,
            "pourcentage": 0
        }
    
    # Vérifier combien de rencontres ont des résultats
    rencontres_avec_resultats = 0
    details_manquants = []
    
    for rencontre in rencontres:
        resultats = db.query(models.Resultat).filter(
            models.Resultat.rencontre_id == rencontre.id
        ).all()
        
        if resultats and len(resultats) > 0:
            rencontres_avec_resultats += 1
        else:
            # Récupérer les noms des joueurs pour le détail
            joueur_names = []
            if rencontre.participants:
                for joueur_id in rencontre.participants:
                    joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first()
                    if joueur:
                        joueur_names.append(f"{joueur.prenom or ''} {joueur.nom or joueur.username}".strip())
            
            details_manquants.append({
                "rencontre_id": rencontre.id,
                "joueurs": joueur_names,
                "poule_id": rencontre.poule_id
            })
    
    total_rencontres = len(rencontres)
    pourcentage = int((rencontres_avec_resultats / total_rencontres) * 100) if total_rencontres > 0 else 0
    complete = rencontres_avec_resultats == total_rencontres
    
    return {
        "complete": complete,
        "total_rencontres": total_rencontres,
        "rencontres_terminees": rencontres_avec_resultats,
        "pourcentage": pourcentage,
        "rencontres_manquantes": details_manquants if not complete else []
    }

@router.put("/evenements/{evenement_id}/phases/reorder")
def reorder_phases(evenement_id: str, phase_orders: List[Dict], db: Session = Depends(get_db)):
    """Réorganise l'ordre des phases d'un événement
    
    Body attendu : [{"phase_id": "uuid", "ordre": 1}, {"phase_id": "uuid2", "ordre": 2}, ...]
    """
    # Vérifier que l'événement existe
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Mettre à jour l'ordre de chaque phase
    for phase_order in phase_orders:
        phase_id = phase_order.get("phase_id")
        ordre = phase_order.get("ordre")
        
        if not phase_id or ordre is None:
            raise HTTPException(status_code=400, detail="phase_id et ordre requis pour chaque élément")
        
        # Vérifier que la phase existe dans cet événement
        phase_in_event = db.execute(
            select(models.phase_evenement).where(
                models.phase_evenement.c.phase_id == phase_id,
                models.phase_evenement.c.evenement_id == evenement_id
            )
        ).first()
        
        if not phase_in_event:
            raise HTTPException(status_code=404, detail=f"Phase {phase_id} non trouvée dans cet événement")
        
        # Mettre à jour l'ordre
        db.execute(
            models.phase_evenement.update().where(
                models.phase_evenement.c.phase_id == phase_id,
                models.phase_evenement.c.evenement_id == evenement_id
            ).values(ordre=ordre)
        )
    
    db.commit()
    return {"message": "Ordre des phases mis à jour"}

@router.post("/evenements/{evenement_id}/phases/{phase_id}/qualifier")
def qualifier_pour_phase_suivante(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Qualifie automatiquement les joueurs pour la phase suivante selon les règles de qualification"""
    
    # 1. Récupérer la phase actuelle avec sa config_qualification
    phase_actuelle = db.execute(
        select(models.phase_evenement).where(
            models.phase_evenement.c.phase_id == phase_id,
            models.phase_evenement.c.evenement_id == evenement_id
        )
    ).first()
    
    if not phase_actuelle:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    config_qualification = phase_actuelle.config_qualification
    if not config_qualification or config_qualification.get('mode') == 'aucune':
        raise HTTPException(status_code=400, detail="Aucune configuration de qualification pour cette phase")
    
    # 2. Récupérer la phase suivante (ordre + 1)
    phase_suivante = db.execute(
        select(models.phase_evenement).where(
            models.phase_evenement.c.evenement_id == evenement_id,
            models.phase_evenement.c.ordre == phase_actuelle.ordre + 1
        )
    ).first()
    
    if not phase_suivante:
        raise HTTPException(status_code=404, detail="Aucune phase suivante configurée")
    
    # 3. Récupérer les informations de la phase pour le scoring
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if not db_phase:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    # 4. Calculer le classement selon le mode de qualification
    mode = config_qualification.get('mode')
    joueurs_qualifies = []
    
    if mode == 'tous_qualifies':
        # Tous les joueurs passent à la phase suivante
        joueurs_inscrits = db.execute(
            select(models.phase_evenement_joueur).where(
                models.phase_evenement_joueur.c.phase_id == phase_id,
                models.phase_evenement_joueur.c.evenement_id == evenement_id
            )
        ).all()
        joueurs_qualifies = [j.joueur_id for j in joueurs_inscrits]
    
    elif mode in ['classement_phase', 'par_poule']:
        # Calculer le classement basé sur les résultats de cette phase
        classement = calculer_classement_phase(phase_id, evenement_id, db_phase, db)
        
        # Appliquer les critères de sélection
        nb_qualifies = config_qualification.get('nb_qualifies')
        pourcentage_qualifies = config_qualification.get('pourcentage_qualifies')
        
        if nb_qualifies:
            # Nombre fixe de qualifiés
            joueurs_qualifies = [j['joueur_id'] for j in classement[:nb_qualifies]]
        elif pourcentage_qualifies:
            # Pourcentage de qualifiés
            nb_total = len(classement)
            nb_a_qualifier = int(nb_total * pourcentage_qualifies / 100)
            joueurs_qualifies = [j['joueur_id'] for j in classement[:nb_a_qualifier]]
        else:
            raise HTTPException(status_code=400, detail="Configuration de qualification invalide")
    
    elif mode == 'classement_general':
        # TODO: Implémenter le classement général cumulé sur toutes les phases précédentes
        raise HTTPException(status_code=501, detail="Le mode 'classement_general' n'est pas encore implémenté")
    
    # 5. Inscrire les joueurs qualifiés à la phase suivante
    ordre_inscription = 1
    for joueur_id in joueurs_qualifies:
        # Vérifier si pas déjà inscrit
        existing = db.execute(
            select(models.phase_evenement_joueur).where(
                models.phase_evenement_joueur.c.phase_id == phase_suivante.phase_id,
                models.phase_evenement_joueur.c.evenement_id == evenement_id,
                models.phase_evenement_joueur.c.joueur_id == joueur_id
            )
        ).first()
        
        if not existing:
            db.execute(
                models.phase_evenement_joueur.insert().values(
                    phase_id=phase_suivante.phase_id,
                    evenement_id=evenement_id,
                    joueur_id=joueur_id,
                    ordre_inscription=ordre_inscription,
                    statut='qualifie',
                    phase_origine_id=phase_id  # Tracer d'où vient la qualification
                )
            )
            ordre_inscription += 1
    
    db.commit()
    
    return {
        "message": "Qualification effectuée avec succès",
        "phase_actuelle": phase_id,
        "phase_suivante": phase_suivante.phase_id,
        "joueurs_qualifies": len(joueurs_qualifies),
        "mode": mode
    }

def calculer_classement_phase(phase_id: str, evenement_id: str, db_phase: models.Phase, db: Session) -> List[Dict]:
    """Calcule le classement d'une phase selon les règles de scoring configurées"""
    
    # Récupérer tous les joueurs de la phase
    joueurs_inscrits = db.execute(
        select(models.phase_evenement_joueur).where(
            models.phase_evenement_joueur.c.phase_id == phase_id,
            models.phase_evenement_joueur.c.evenement_id == evenement_id
        )
    ).all()
    
    if not joueurs_inscrits:
        return []
    
    # Initialiser le classement
    classement = {}
    for inscription in joueurs_inscrits:
        joueur_id = inscription.joueur_id
        classement[joueur_id] = {
            'joueur_id': joueur_id,
            'victoires': 0,
            'rencontres_jouees': 0,
            'touches_donnees': 0,
            'touches_recues': 0,
            'vm': 0,
            'indice': 0
        }
    
    # Récupérer toutes les rencontres de cette phase
    rencontres = db.query(models.Rencontre).filter(
        models.Rencontre.phase_id == phase_id,
        models.Rencontre.evenement_id == evenement_id
    ).all()
    
    # Calculer les statistiques pour chaque joueur
    for rencontre in rencontres:
        resultats = db.query(models.Resultat).filter(
            models.Resultat.rencontre_id == rencontre.id
        ).all()
        
        if len(resultats) == 2:
            r1, r2 = resultats[0], resultats[1]
            
            # Joueur 1
            if r1.joueur_id in classement:
                classement[r1.joueur_id]['rencontres_jouees'] += 1
                classement[r1.joueur_id]['touches_donnees'] += r1.score or 0
                classement[r1.joueur_id]['touches_recues'] += r2.score or 0
                if (r1.score or 0) > (r2.score or 0):
                    classement[r1.joueur_id]['victoires'] += 1
            
            # Joueur 2
            if r2.joueur_id in classement:
                classement[r2.joueur_id]['rencontres_jouees'] += 1
                classement[r2.joueur_id]['touches_donnees'] += r2.score or 0
                classement[r2.joueur_id]['touches_recues'] += r1.score or 0
                if (r2.score or 0) > (r1.score or 0):
                    classement[r2.joueur_id]['victoires'] += 1
    
    # Calculer V/M et indice
    for joueur_id in classement:
        rencontres = classement[joueur_id]['rencontres_jouees']
        if rencontres > 0:
            classement[joueur_id]['vm'] = classement[joueur_id]['victoires'] / rencontres
        classement[joueur_id]['indice'] = classement[joueur_id]['touches_donnees'] - classement[joueur_id]['touches_recues']
    
    # Récupérer l'ordre de priorité du scoring
    scoring = db_phase.scoring or {}
    ordre_priorite = scoring.get('ordrePriorite', ['Points de Victoire', 'V/M', 'Indice (GoalAverage)', 'Points mis'])
    
    # Mapping des critères
    critere_mapping = {
        'Points de Victoire': lambda x: -x['victoires'],
        'V/M': lambda x: -x['vm'],
        'Indice (GoalAverage)': lambda x: -x['indice'],
        'Points mis': lambda x: -x['touches_donnees'],
        'Points Pris': lambda x: -x['touches_recues']
    }
    
    # Construire la clé de tri
    def build_sort_key(joueur):
        return tuple(critere_mapping.get(critere, lambda x: 0)(joueur) for critere in ordre_priorite)
    
    # Trier et retourner
    classement_list = sorted(classement.values(), key=build_sort_key)
    
    return classement_list