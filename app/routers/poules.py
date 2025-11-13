from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from .. import models
from ..database import get_db
import uuid

router = APIRouter()

@router.post("/evenements/{evenement_id}/phases/{phase_id}/poules/generer")
def generer_poules_automatique(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Génère automatiquement les poules selon la configuration de la phase"""
    
    # Récupérer la phase avec sa configuration
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if not db_phase:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    # Récupérer la configuration de poule depuis phase.configuration
    config = db_phase.configuration or {}
    joueurs_min = config.get('min_joueurs_poule', 2)
    joueurs_max = config.get('max_joueurs_poule', 8)
    joueurs_souhaite = config.get('ideal_joueurs_poule', 6)
    
    # Récupérer tous les joueurs inscrits à cette phase
    joueurs_inscrits = db.execute(
        models.phase_evenement_joueur.select().where(
            models.phase_evenement_joueur.c.phase_id == phase_id,
            models.phase_evenement_joueur.c.evenement_id == evenement_id
        ).order_by(models.phase_evenement_joueur.c.ordre_inscription)
    ).all()
    
    if not joueurs_inscrits:
        raise HTTPException(status_code=400, detail="Aucun joueur inscrit à cette phase")
    
    nb_joueurs = len(joueurs_inscrits)
    
    # Calculer le nombre optimal de poules
    nb_poules = calcul_nombre_poules(nb_joueurs, joueurs_min, joueurs_max, joueurs_souhaite)
    
    # Supprimer les poules existantes pour cette phase
    poules_existantes = db.query(models.Poule).filter(
        models.Poule.phase_id == phase_id,
        models.Poule.evenement_id == evenement_id
    ).all()
    
    for poule in poules_existantes:
        # Supprimer les associations joueurs
        db.execute(
            models.poule_joueur.delete().where(
                models.poule_joueur.c.poule_id == poule.id
            )
        )
        db.delete(poule)
    
    db.commit()
    
    # Créer les nouvelles poules
    poules = []
    for i in range(nb_poules):
        nom_poule = f"Poule {chr(65 + i)}" if nb_poules <= 26 else f"Poule {i + 1}"
        poule = models.Poule(
            id=str(uuid.uuid4()),
            phase_id=phase_id,
            evenement_id=evenement_id,
            nom=nom_poule,
            ordre=i + 1
        )
        db.add(poule)
        poules.append(poule)
    
    db.commit()
    
    # Répartir les joueurs dans les poules (serpentin pour équilibrer)
    repartition = repartir_joueurs_serpentin(joueurs_inscrits, nb_poules)
    
    for idx_poule, joueurs_poule in enumerate(repartition):
        poule = poules[idx_poule]
        for ordre, inscription in enumerate(joueurs_poule, start=1):
            db.execute(
                models.poule_joueur.insert().values(
                    poule_id=poule.id,
                    joueur_id=inscription.joueur_id,
                    ordre=ordre
                )
            )
    
    db.commit()
    
    # Récupérer les poules créées avec leurs joueurs pour la réponse
    poules_avec_joueurs = []
    for poule in poules:
        joueurs_ids = db.execute(
            models.poule_joueur.select().where(
                models.poule_joueur.c.poule_id == poule.id
            )
        ).all()
        
        joueurs_details = []
        for pj in joueurs_ids:
            joueur = db.query(models.Joueur).filter(models.Joueur.id == pj.joueur_id).first()
            if joueur:
                joueurs_details.append({
                    "id": joueur.id,
                    "username": joueur.username,
                    "ordre": pj.ordre
                })
        
        poules_avec_joueurs.append({
            "id": poule.id,
            "nom": poule.nom,
            "ordre": poule.ordre,
            "joueurs": joueurs_details
        })
    
    return {
        "message": f"{nb_poules} poules créées avec succès",
        "nb_poules": nb_poules,
        "nb_joueurs_total": nb_joueurs,
        "poules": poules_avec_joueurs
    }

def calcul_nombre_poules(nb_joueurs: int, joueurs_min: int, joueurs_max: int, joueurs_souhaite: int) -> int:
    """Calcule le nombre optimal de poules selon les contraintes"""
    
    if nb_joueurs <= joueurs_max:
        # Une seule poule suffit
        return 1
    
    # Essayer de créer des poules avec le nombre souhaité
    nb_poules = nb_joueurs // joueurs_souhaite
    reste = nb_joueurs % joueurs_souhaite
    
    # Si le reste est trop petit, on redistribue
    if reste > 0 and reste < joueurs_min:
        # Ajouter une poule pour accueillir le reste
        nb_poules += 1
    elif reste > 0:
        # Le reste forme une poule valide
        nb_poules += 1
    
    # Vérifier que chaque poule aura au moins joueurs_min
    joueurs_par_poule = nb_joueurs // nb_poules
    if joueurs_par_poule < joueurs_min:
        # Réduire le nombre de poules
        nb_poules = nb_joueurs // joueurs_min
        if nb_joueurs % joueurs_min > 0:
            nb_poules += 1
    
    return max(1, nb_poules)

def repartir_joueurs_serpentin(joueurs_inscrits: List, nb_poules: int) -> List[List]:
    """Répartit les joueurs en serpentin pour équilibrer les poules selon les seeds"""
    
    poules = [[] for _ in range(nb_poules)]
    
    # Méthode serpentin : 
    # Poule A: 1, 8, 9, 16, 17...
    # Poule B: 2, 7, 10, 15, 18...
    # Poule C: 3, 6, 11, 14, 19...
    # Poule D: 4, 5, 12, 13, 20...
    
    for idx, joueur in enumerate(joueurs_inscrits):
        # Calculer dans quelle poule mettre ce joueur
        cycle = idx // nb_poules
        position_in_cycle = idx % nb_poules
        
        # Alterner la direction : pair = normal, impair = inversé
        if cycle % 2 == 0:
            poule_index = position_in_cycle
        else:
            poule_index = nb_poules - 1 - position_in_cycle
        
        poules[poule_index].append(joueur)
    
    return poules

@router.get("/evenements/{evenement_id}/phases/{phase_id}/poules")
def lister_poules(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Liste toutes les poules d'une phase avec leurs joueurs"""
    
    poules = db.query(models.Poule).filter(
        models.Poule.phase_id == phase_id,
        models.Poule.evenement_id == evenement_id
    ).order_by(models.Poule.ordre).all()
    
    result = []
    for poule in poules:
        # Récupérer les joueurs de la poule
        joueurs_poule = db.execute(
            models.poule_joueur.select().where(
                models.poule_joueur.c.poule_id == poule.id
            ).order_by(models.poule_joueur.c.ordre)
        ).all()
        
        joueurs_details = []
        for pj in joueurs_poule:
            joueur = db.query(models.Joueur).filter(models.Joueur.id == pj.joueur_id).first()
            if joueur:
                joueurs_details.append({
                    "id": joueur.id,
                    "username": joueur.username,
                    "prenom": joueur.prenom,
                    "nom": joueur.nom,
                    "club": joueur.club,
                    "ordre": pj.ordre
                })
        
        result.append({
            "id": poule.id,
            "nom": poule.nom,
            "ordre": poule.ordre,
            "nb_joueurs": len(joueurs_details),
            "joueurs": joueurs_details
        })
    
    return result

@router.delete("/evenements/{evenement_id}/phases/{phase_id}/poules/{poule_id}")
def supprimer_poule(evenement_id: str, phase_id: str, poule_id: str, db: Session = Depends(get_db)):
    """Supprime une poule"""
    
    poule = db.query(models.Poule).filter(
        models.Poule.id == poule_id,
        models.Poule.phase_id == phase_id,
        models.Poule.evenement_id == evenement_id
    ).first()
    
    if not poule:
        raise HTTPException(status_code=404, detail="Poule non trouvée")
    
    # Supprimer les associations
    db.execute(
        models.poule_joueur.delete().where(
            models.poule_joueur.c.poule_id == poule_id
        )
    )
    
    db.delete(poule)
    db.commit()
    
    return {"message": "Poule supprimée"}

@router.post("/evenements/{evenement_id}/phases/{phase_id}/poules/{poule_id}/joueurs/{joueur_id}")
def ajouter_joueur_poule(evenement_id: str, phase_id: str, poule_id: str, joueur_id: str, db: Session = Depends(get_db)):
    """Ajoute un joueur à une poule"""
    
    # Vérifier que la poule existe
    poule = db.query(models.Poule).filter(
        models.Poule.id == poule_id,
        models.Poule.phase_id == phase_id
    ).first()
    
    if not poule:
        raise HTTPException(status_code=404, detail="Poule non trouvée")
    
    # Vérifier que le joueur est inscrit à la phase
    inscription = db.execute(
        models.phase_evenement_joueur.select().where(
            models.phase_evenement_joueur.c.phase_id == phase_id,
            models.phase_evenement_joueur.c.evenement_id == evenement_id,
            models.phase_evenement_joueur.c.joueur_id == joueur_id
        )
    ).first()
    
    if not inscription:
        raise HTTPException(status_code=400, detail="Joueur non inscrit à cette phase")
    
    # Vérifier si déjà dans cette poule
    existing = db.execute(
        models.poule_joueur.select().where(
            models.poule_joueur.c.poule_id == poule_id,
            models.poule_joueur.c.joueur_id == joueur_id
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Joueur déjà dans cette poule")
    
    # Calculer le prochain ordre
    max_ordre = db.execute(
        models.poule_joueur.select().where(
            models.poule_joueur.c.poule_id == poule_id
        )
    ).all()
    
    next_ordre = len(max_ordre) + 1
    
    # Ajouter le joueur
    db.execute(
        models.poule_joueur.insert().values(
            poule_id=poule_id,
            joueur_id=joueur_id,
            ordre=next_ordre
        )
    )
    
    db.commit()
    
    return {"message": "Joueur ajouté à la poule"}

@router.delete("/evenements/{evenement_id}/phases/{phase_id}/poules/{poule_id}/joueurs/{joueur_id}")
def retirer_joueur_poule(evenement_id: str, phase_id: str, poule_id: str, joueur_id: str, db: Session = Depends(get_db)):
    """Retire un joueur d'une poule"""
    
    result = db.execute(
        models.poule_joueur.delete().where(
            models.poule_joueur.c.poule_id == poule_id,
            models.poule_joueur.c.joueur_id == joueur_id
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Joueur non trouvé dans cette poule")
    
    db.commit()
    
    return {"message": "Joueur retiré de la poule"}
