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
    
    # Récupérer la configuration des décalages depuis phase_evenement
    phase_event_rel = db.execute(
        models.phase_evenement.select().where(
            models.phase_evenement.c.phase_id == phase_id,
            models.phase_evenement.c.evenement_id == evenement_id
        )
    ).first()
    
    config_decalages = {}
    if phase_event_rel and phase_event_rel.config_qualification:
        config_decalages = phase_event_rel.config_qualification.get('decalages', {})
    
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
        # Supprimer les rencontres de cette poule (et leurs résultats via CASCADE)
        rencontres_poule = db.query(models.Rencontre).filter(
            models.Rencontre.poule_id == poule.id
        ).all()
        
        for rencontre in rencontres_poule:
            # Supprimer les résultats de la rencontre (CASCADE devrait le faire mais on force)
            db.query(models.Resultat).filter(
                models.Resultat.rencontre_id == rencontre.id
            ).delete()
            db.delete(rencontre)
        
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
        nom_poule = f"Poule {i + 1}"
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
    
    # Répartir les joueurs dans les poules avec décalages intelligents (éviter même club/nation)
    repartition = repartir_joueurs_serpentin(joueurs_inscrits, nb_poules, db=db, config_decalages=config_decalages)
    
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
    
    # ÉTAPE 3 : Générer les rencontres PAR POULE (tous contre tous)
    import itertools
    rencontres_creees = 0
    for poule in poules:
        # Récupérer les joueurs de cette poule
        joueurs_poule = db.execute(
            models.poule_joueur.select().where(
                models.poule_joueur.c.poule_id == poule.id
            ).order_by(models.poule_joueur.c.ordre)
        ).all()
        
        joueur_ids = [j.joueur_id for j in joueurs_poule]
        
        # Générer tous contre tous dans cette poule
        for joueur1_id, joueur2_id in itertools.combinations(joueur_ids, 2):
            rencontre = models.Rencontre(
                id=str(uuid.uuid4()),
                phase_id=phase_id,
                evenement_id=evenement_id,
                participants=[joueur1_id, joueur2_id],
                poule_id=poule.id
            )
            db.add(rencontre)
            rencontres_creees += 1
    
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
        "message": f"{nb_poules} poules et {rencontres_creees} rencontres créées avec succès",
        "nb_poules": nb_poules,
        "nb_joueurs_total": nb_joueurs,
        "rencontres_creees": rencontres_creees,
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

def repartir_joueurs_serpentin(joueurs_inscrits: List, nb_poules: int, db: Session = None, config_decalages: dict = None) -> List[List]:
    """
    Répartit les joueurs en serpentin avec décalages intelligents.
    Évite de mettre des joueurs du même club ou de la même nation dans la même poule selon la configuration.
    """
    from collections import defaultdict
    
    poules = [[] for _ in range(nb_poules)]
    
    # Si pas de configuration de décalages ou pas de DB, faire la répartition simple en serpentin
    if db is None or not config_decalages or (not config_decalages.get('decalage_club') and not config_decalages.get('decalage_nation')):
        for idx, joueur in enumerate(joueurs_inscrits):
            cycle = idx // nb_poules
            position_in_cycle = idx % nb_poules
            
            if cycle % 2 == 0:
                poule_index = position_in_cycle
            else:
                poule_index = nb_poules - 1 - position_in_cycle
            
            poules[poule_index].append(joueur)
        return poules
    
    # Récupérer les détails des joueurs (club, nation) en une seule requête
    joueur_ids = [j.joueur_id for j in joueurs_inscrits]
    joueurs_details = db.query(models.Joueur).filter(models.Joueur.id.in_(joueur_ids)).all()
    joueurs_dict = {j.id: j for j in joueurs_details}
    
    # Fonction pour calculer un score de conflit pour une poule
    def score_conflit(poule, nouveau_joueur_id):
        """
        Calcule un score de conflit : plus le score est élevé, plus il y a de conflits.
        Retourne le nombre de joueurs avec le même club + nombre avec la même nation (selon config).
        """
        if not poule:
            return 0
        
        nouveau_joueur = joueurs_dict.get(nouveau_joueur_id)
        if not nouveau_joueur:
            return 0
        
        conflits = 0
        for inscription in poule:
            joueur = joueurs_dict.get(inscription.joueur_id)
            if not joueur:
                continue
            
            # Conflit de club (poids 2) - seulement si activé dans config
            if config_decalages.get('decalage_club'):
                if nouveau_joueur.club and joueur.club and nouveau_joueur.club.strip().lower() == joueur.club.strip().lower():
                    conflits += 2
            
            # Conflit de nation (poids 1) - seulement si activé dans config
            if config_decalages.get('decalage_nation'):
                if hasattr(nouveau_joueur, 'nation') and hasattr(joueur, 'nation'):
                    if nouveau_joueur.nation and joueur.nation and nouveau_joueur.nation.strip().lower() == joueur.nation.strip().lower():
                        conflits += 1
        
        return conflits
    
    # Répartir les joueurs en cherchant la meilleure poule pour chaque joueur
    for idx, inscription in enumerate(joueurs_inscrits):
        # Calculer la position serpentin de base
        cycle = idx // nb_poules
        position_in_cycle = idx % nb_poules
        
        if cycle % 2 == 0:
            poule_base = position_in_cycle
        else:
            poule_base = nb_poules - 1 - position_in_cycle
        
        # Chercher la poule avec le moins de conflits (dans un rayon de +/- 2 autour de la position de base)
        meilleures_poules = []
        min_conflit = float('inf')
        
        # Tester la poule de base et ses voisines
        for offset in [0, 1, -1, 2, -2]:
            poule_idx = (poule_base + offset) % nb_poules
            conflit = score_conflit(poules[poule_idx], inscription.joueur_id)
            
            if conflit < min_conflit:
                min_conflit = conflit
                meilleures_poules = [poule_idx]
            elif conflit == min_conflit:
                meilleures_poules.append(poule_idx)
        
        # Si plusieurs poules ont le même score, prendre la plus vide pour équilibrer
        if len(meilleures_poules) > 1:
            poule_choisie = min(meilleures_poules, key=lambda p: len(poules[p]))
        else:
            poule_choisie = meilleures_poules[0]
        
        poules[poule_choisie].append(inscription)
    
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
