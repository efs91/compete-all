from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import delete
from typing import List
from .. import models, schemas
from ..database import get_db
import uuid
import itertools

router = APIRouter()

@router.post("/", response_model=schemas.Evenement)
def create_evenement(evenement: schemas.EvenementCreate, db: Session = Depends(get_db)):
    db_evenement = models.Evenement(**evenement.dict())
    db.add(db_evenement)
    db.commit()
    db.refresh(db_evenement)
    return db_evenement

@router.get("/", response_model=List[schemas.Evenement])
def read_evenements(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    evenements = db.query(models.Evenement).offset(skip).limit(limit).all()
    return evenements

@router.get("/{evenement_id}", response_model=schemas.Evenement)
def read_evenement(evenement_id: str, db: Session = Depends(get_db)):
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    return db_evenement

@router.put("/{evenement_id}", response_model=schemas.Evenement)
def update_evenement(evenement_id: str, evenement: schemas.EvenementCreate, db: Session = Depends(get_db)):
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    for key, value in evenement.dict().items():
        setattr(db_evenement, key, value)
    
    db.commit()
    db.refresh(db_evenement)
    return db_evenement

@router.delete("/{evenement_id}")
def delete_evenement(evenement_id: str, db: Session = Depends(get_db)):
    """Supprime un événement et TOUTES ses données associées (phases, rencontres, résultats, classements, inscriptions)"""
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if db_evenement is None:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # 1. Récupérer toutes les rencontres de cet événement
    rencontres = db.query(models.Rencontre).filter(
        models.Rencontre.evenement_id == evenement_id
    ).all()
    rencontre_ids = [r.id for r in rencontres]
    
    if rencontre_ids:
        # 2. Supprimer tous les résultats
        db.query(models.Resultat).filter(
            models.Resultat.rencontre_id.in_(rencontre_ids)
        ).delete(synchronize_session=False)
        
        # 3. Supprimer les classements liés aux rencontres
        db.query(models.Classement).filter(
            models.Classement.rencontre_id.in_(rencontre_ids)
        ).delete(synchronize_session=False)
        
        # 4. Supprimer toutes les rencontres
        db.query(models.Rencontre).filter(
            models.Rencontre.evenement_id == evenement_id
        ).delete(synchronize_session=False)
    
    # 5. Supprimer les classements liés à l'événement
    db.query(models.Classement).filter(
        models.Classement.evenement_id == evenement_id
    ).delete(synchronize_session=False)
    
    # 6. Supprimer les associations poule_joueur
    poules = db.query(models.Poule).filter(models.Poule.evenement_id == evenement_id).all()
    poule_ids = [p.id for p in poules]
    if poule_ids:
        db.execute(
            models.poule_joueur.delete().where(
                models.poule_joueur.c.poule_id.in_(poule_ids)
            )
        )
    
    # 7. Supprimer les poules
    db.query(models.Poule).filter(
        models.Poule.evenement_id == evenement_id
    ).delete(synchronize_session=False)
    
    # 8. Supprimer les équipes de l'événement
    db.query(models.Equipe).filter(
        models.Equipe.evenement_id == evenement_id
    ).delete(synchronize_session=False)
    
    # 9. Supprimer les inscriptions joueurs (phase_evenement_joueur)
    db.execute(
        models.phase_evenement_joueur.delete().where(
            models.phase_evenement_joueur.c.evenement_id == evenement_id
        )
    )
    
    # 10. Supprimer les relations phases-événement
    db.execute(
        models.phase_evenement.delete().where(
            models.phase_evenement.c.evenement_id == evenement_id
        )
    )
    
    # 11. Enfin, supprimer l'événement lui-même
    db.delete(db_evenement)
    db.commit()
    return {"message": "Événement et toutes ses données supprimés"}

# ============================================
# GESTION DES INSCRIPTIONS À UN ÉVÉNEMENT
# ============================================

@router.post("/{evenement_id}/inscriptions/{joueur_id}")
def inscrire_joueur_evenement(evenement_id: str, joueur_id: str, db: Session = Depends(get_db)):
    """Inscrit un joueur à un événement"""
    # Vérifier que l'événement existe
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if not db_evenement:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Vérifier que le joueur existe
    db_joueur = db.query(models.Joueur).filter(models.Joueur.id == joueur_id).first()
    if not db_joueur:
        raise HTTPException(status_code=404, detail="Joueur non trouvé")
    
    # Vérifier si déjà inscrit
    existing = db.execute(
        models.evenement_joueur.select().where(
            models.evenement_joueur.c.evenement_id == evenement_id,
            models.evenement_joueur.c.joueur_id == joueur_id
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Joueur déjà inscrit à cet événement")
    
    # Inscrire le joueur
    db.execute(
        models.evenement_joueur.insert().values(
            evenement_id=evenement_id,
            joueur_id=joueur_id
        )
    )
    db.commit()
    
    return {"message": "Joueur inscrit à l'événement", "joueur": db_joueur}

@router.delete("/{evenement_id}/inscriptions/{joueur_id}")
def desinscrire_joueur_evenement(evenement_id: str, joueur_id: str, db: Session = Depends(get_db)):
    """Désinscrit un joueur d'un événement"""
    result = db.execute(
        models.evenement_joueur.delete().where(
            models.evenement_joueur.c.evenement_id == evenement_id,
            models.evenement_joueur.c.joueur_id == joueur_id
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Joueur non inscrit à cet événement")
    
    db.commit()
    return {"message": "Joueur désinscrit de l'événement"}

@router.get("/{evenement_id}/inscriptions")
def lister_inscrits_evenement(evenement_id: str, db: Session = Depends(get_db)):
    """Liste tous les joueurs inscrits à un événement"""
    # Vérifier que l'événement existe
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if not db_evenement:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Récupérer les IDs des joueurs inscrits
    inscriptions = db.execute(
        models.evenement_joueur.select().where(
            models.evenement_joueur.c.evenement_id == evenement_id
        )
    ).all()
    
    joueur_ids = [i.joueur_id for i in inscriptions]
    
    # Récupérer les détails des joueurs
    joueurs = db.query(models.Joueur).filter(models.Joueur.id.in_(joueur_ids)).all()
    
    return joueurs

@router.post("/{evenement_id}/lancer")
def lancer_competition(evenement_id: str, db: Session = Depends(get_db)):
    """Lance la compétition en inscrivant tous les joueurs de l'événement à la première phase"""
    # Vérifier que l'événement existe
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if not db_evenement:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Récupérer la première phase (ordre le plus petit)
    premiere_phase = db.execute(
        models.phase_evenement.select().where(
            models.phase_evenement.c.evenement_id == evenement_id
        ).order_by(models.phase_evenement.c.ordre)
    ).first()
    
    if not premiere_phase:
        raise HTTPException(status_code=404, detail="Aucune phase configurée pour cet événement")
    
    phase_id = premiere_phase.phase_id
    
    # Récupérer tous les joueurs inscrits à l'événement
    inscriptions = db.execute(
        models.evenement_joueur.select().where(
            models.evenement_joueur.c.evenement_id == evenement_id
        )
    ).all()
    
    if not inscriptions:
        raise HTTPException(status_code=400, detail="Aucun joueur inscrit à l'événement")
    
    # Inscrire chaque joueur à la première phase
    joueurs_inscrits = 0
    for idx, inscription in enumerate(inscriptions, start=1):
        # Vérifier si déjà inscrit
        existing = db.execute(
            models.phase_evenement_joueur.select().where(
                models.phase_evenement_joueur.c.phase_id == phase_id,
                models.phase_evenement_joueur.c.evenement_id == evenement_id,
                models.phase_evenement_joueur.c.joueur_id == inscription.joueur_id
            )
        ).first()
        
        if not existing:
            db.execute(
                models.phase_evenement_joueur.insert().values(
                    phase_id=phase_id,
                    evenement_id=evenement_id,
                    joueur_id=inscription.joueur_id,
                    ordre_inscription=idx,
                    statut='inscrit',
                    phase_origine_id=None  # Première phase = pas d'origine
                )
            )
            joueurs_inscrits += 1
    
    db.commit()
    
    # ÉTAPE 2 : Générer les poules
    db_phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if not db_phase:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    config = db_phase.configuration or {}
    
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
    
    # Lire les clés correctes depuis la configuration (les noms viennent de l'interface admin)
    joueurs_min = config.get('min_joueurs_poule', config.get('joueurs_min', 3))
    joueurs_max = config.get('max_joueurs_poule', config.get('joueurs_max', 8))
    joueurs_souhaite = config.get('ideal_joueurs_poule', config.get('joueurs_souhaite', 6))
    
    nb_joueurs = len(inscriptions)
    nb_poules = calcul_nombre_poules_helper(nb_joueurs, joueurs_min, joueurs_max, joueurs_souhaite)
    
    # Supprimer les poules existantes
    poules_existantes = db.query(models.Poule).filter(
        models.Poule.phase_id == phase_id,
        models.Poule.evenement_id == evenement_id
    ).all()
    
    for poule in poules_existantes:
        db.execute(models.poule_joueur.delete().where(models.poule_joueur.c.poule_id == poule.id))
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
    
    # Répartir les joueurs en serpentin avec décalages intelligents (éviter même club/nation)
    joueurs_phase = list(inscriptions)
    repartition = repartir_joueurs_serpentin_helper(joueurs_phase, nb_poules, db=db, config_decalages=config_decalages)
    
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
    
    # ÉTAPE 3 : Générer les rencontres PAR POULE
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
    
    # Mettre à jour le statut de l'événement
    db_evenement.statut = 'lance'
    db.commit()
    
    return {
        "message": "Compétition lancée avec succès",
        "phase_id": phase_id,
        "joueurs_inscrits": joueurs_inscrits,
        "total_joueurs": len(inscriptions),
        "nb_poules": nb_poules,
        "rencontres_creees": rencontres_creees
    }

@router.post("/{evenement_id}/relancer")
def relancer_competition(evenement_id: str, db: Session = Depends(get_db)):
    """Relance la compétition : supprime toutes les données (poules, rencontres, résultats) et remet le statut à 'brouillon'"""
    # Vérifier que l'événement existe
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if not db_evenement:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Récupérer toutes les rencontres de l'événement
    rencontres = db.query(models.Rencontre).filter(models.Rencontre.evenement_id == evenement_id).all()
    
    # Supprimer tous les résultats de ces rencontres
    for rencontre in rencontres:
        db.query(models.Resultat).filter(models.Resultat.rencontre_id == rencontre.id).delete()
    
    # Supprimer toutes les rencontres de l'événement
    db.query(models.Rencontre).filter(models.Rencontre.evenement_id == evenement_id).delete()
    
    # Supprimer toutes les associations poule_joueur pour cet événement
    poules = db.query(models.Poule).filter(models.Poule.evenement_id == evenement_id).all()
    for poule in poules:
        db.execute(models.poule_joueur.delete().where(models.poule_joueur.c.poule_id == poule.id))
    
    # Supprimer toutes les poules de l'événement
    db.query(models.Poule).filter(models.Poule.evenement_id == evenement_id).delete()
    
    # Supprimer TOUTES les inscriptions aux phases (on recommence de zéro)
    # Les joueurs inscrits à l'événement restent, mais plus dans les phases
    stmt = delete(models.phase_evenement_joueur).where(
        models.phase_evenement_joueur.c.evenement_id == evenement_id
    )
    db.execute(stmt)
    
    # Remettre le statut de l'événement à 'brouillon'
    db_evenement.statut = 'brouillon'
    
    db.commit()
    
    return {
        "message": "Compétition relancée : toutes les données ont été supprimées",
        "statut": "brouillon"
    }

def calcul_nombre_poules_helper(nb_joueurs: int, joueurs_min: int, joueurs_max: int, joueurs_souhaite: int) -> int:
    """Calcule le nombre optimal de poules selon les contraintes"""
    
    # Cas simple : une seule poule suffit SI on est dans les limites
    if nb_joueurs >= joueurs_min and nb_joueurs <= joueurs_max:
        return 1
    
    # Calculer le nombre minimum de poules nécessaire pour respecter le max
    nb_poules_min = (nb_joueurs + joueurs_max - 1) // joueurs_max  # Arrondi supérieur
    
    # Calculer le nombre idéal basé sur le nombre souhaité
    nb_poules_ideal = (nb_joueurs + joueurs_souhaite - 1) // joueurs_souhaite
    
    # Prendre le maximum entre les deux pour garantir qu'on respecte la contrainte max
    nb_poules = max(nb_poules_min, nb_poules_ideal)
    
    # Vérifier que chaque poule aura au moins le minimum
    while nb_poules > 1:
        joueurs_par_poule_min = nb_joueurs // nb_poules
        joueurs_par_poule_max = (nb_joueurs + nb_poules - 1) // nb_poules
        
        # Si même avec répartition équitable on dépasse le max, augmenter le nb de poules
        if joueurs_par_poule_max > joueurs_max:
            nb_poules += 1
        # Si la plus petite poule est trop petite, réduire le nb de poules
        elif joueurs_par_poule_min < joueurs_min:
            nb_poules -= 1
        else:
            break
    
    return max(1, nb_poules)

def repartir_joueurs_serpentin_helper(joueurs_inscrits: List, nb_poules: int, db: Session = None, config_decalages: dict = None) -> List[List]:
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
        
        # Chercher la poule avec le moins de conflits (dans un rayon de +/- 1 autour de la position de base)
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

@router.post("/{evenement_id}/phases/{phase_id}/progresser")
def progresser_vers_phase_suivante(evenement_id: str, phase_id: str, db: Session = Depends(get_db)):
    """Progresse vers la phase suivante : qualifie les joueurs et lance la phase suivante"""
    
    # 1. Vérifier que l'événement et la phase existent
    db_evenement = db.query(models.Evenement).filter(models.Evenement.id == evenement_id).first()
    if not db_evenement:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # 2. Vérifier que la phase actuelle est complète
    phase_event_rel = db.execute(
        models.phase_evenement.select().where(
            models.phase_evenement.c.phase_id == phase_id,
            models.phase_evenement.c.evenement_id == evenement_id
        )
    ).first()
    
    if not phase_event_rel:
        raise HTTPException(status_code=404, detail="Phase non trouvée dans cet événement")
    
    # Vérifier que toutes les rencontres ont des résultats
    rencontres = db.query(models.Rencontre).filter(
        models.Rencontre.phase_id == phase_id,
        models.Rencontre.evenement_id == evenement_id
    ).all()
    
    if not rencontres:
        raise HTTPException(status_code=400, detail="Aucune rencontre dans cette phase")
    
    rencontres_sans_resultats = []
    for rencontre in rencontres:
        resultats = db.query(models.Resultat).filter(models.Resultat.rencontre_id == rencontre.id).count()
        if resultats == 0:
            rencontres_sans_resultats.append(rencontre.id)
    
    if rencontres_sans_resultats:
        raise HTTPException(
            status_code=400, 
            detail=f"La phase n'est pas complète : {len(rencontres_sans_resultats)} rencontre(s) sans résultats"
        )
    
    # 3. Récupérer la phase suivante
    phase_suivante = db.execute(
        models.phase_evenement.select().where(
            models.phase_evenement.c.evenement_id == evenement_id,
            models.phase_evenement.c.ordre == phase_event_rel.ordre + 1
        )
    ).first()
    
    if not phase_suivante:
        raise HTTPException(status_code=404, detail="Aucune phase suivante configurée")
    
    phase_suivante_id = phase_suivante.phase_id
    
    # 4. Calculer les qualifiés selon la configuration
    config_qualification = phase_event_rel.config_qualification or {}
    
    # Le client envoie 'mode' mais on cherche aussi 'mode_qualification' pour rétrocompatibilité
    mode = config_qualification.get('mode', config_qualification.get('mode_qualification', 'par_poule'))
    
    joueurs_qualifies = []
    
    # Calculer le classement général de la phase (on en aura besoin dans tous les cas)
    classement_general = calculer_classement_phase_helper(phase_id, evenement_id, db)
    
    if mode == 'tous_qualifies':
        # TOUS les joueurs sont qualifiés (100%)
        joueurs_qualifies = classement_general
    
    elif mode == 'par_poule':
        # Qualification par poule - X meilleurs de chaque poule
        nb_qualifies_par_poule = config_qualification.get('nb_qualifies', config_qualification.get('nb_qualifies_par_poule', 2))
        
        # Si c'est un pourcentage, calculer le nombre
        if 'pourcentage_qualifies' in config_qualification:
            # On va qualifier un pourcentage par poule
            pourcentage = config_qualification.get('pourcentage_qualifies', 50)
            
            # Récupérer toutes les poules
            poules = db.query(models.Poule).filter(
                models.Poule.phase_id == phase_id,
                models.Poule.evenement_id == evenement_id
            ).all()
            
            for poule in poules:
                classement_poule = calculer_classement_poule_helper(poule.id, phase_id, evenement_id, db)
                nb_dans_poule = len(classement_poule)
                nb_a_qualifier = max(1, int(nb_dans_poule * pourcentage / 100))
                qualifies_poule = classement_poule[:nb_a_qualifier]
                joueurs_qualifies.extend(qualifies_poule)
        else:
            # Nombre fixe par poule
            poules = db.query(models.Poule).filter(
                models.Poule.phase_id == phase_id,
                models.Poule.evenement_id == evenement_id
            ).all()
            
            for poule in poules:
                classement_poule = calculer_classement_poule_helper(poule.id, phase_id, evenement_id, db)
                nb_a_qualifier = min(nb_qualifies_par_poule, len(classement_poule))
                qualifies_poule = classement_poule[:nb_a_qualifier]
                joueurs_qualifies.extend(qualifies_poule)
    
    elif mode in ['classement_phase', 'classement_general', 'total']:
        # Qualification sur le classement général de la phase
        nb_qualifies = config_qualification.get('nb_qualifies', config_qualification.get('nb_qualifies_total', 8))
        
        # Si c'est un pourcentage
        if 'pourcentage_qualifies' in config_qualification:
            pourcentage = config_qualification.get('pourcentage_qualifies', 50)
            nb_total = len(classement_general)
            nb_qualifies = max(1, int(nb_total * pourcentage / 100))
        
        # Prendre les N premiers du classement général
        joueurs_qualifies = classement_general[:nb_qualifies]
    
    if not joueurs_qualifies:
        raise HTTPException(status_code=400, detail="Aucun joueur qualifié")
    
    # 5. Inscrire les qualifiés dans la phase suivante
    joueurs_inscrits_count = 0
    for idx, joueur_data in enumerate(joueurs_qualifies, start=1):
        joueur_id = joueur_data['joueur_id']
        
        # Vérifier si déjà inscrit
        existing = db.execute(
            models.phase_evenement_joueur.select().where(
                models.phase_evenement_joueur.c.phase_id == phase_suivante_id,
                models.phase_evenement_joueur.c.evenement_id == evenement_id,
                models.phase_evenement_joueur.c.joueur_id == joueur_id
            )
        ).first()
        
        if not existing:
            db.execute(
                models.phase_evenement_joueur.insert().values(
                    phase_id=phase_suivante_id,
                    evenement_id=evenement_id,
                    joueur_id=joueur_id,
                    ordre_inscription=idx,
                    statut='qualifie',
                    phase_origine_id=phase_id
                )
            )
            joueurs_inscrits_count += 1
    
    db.commit()
    
    # 6. Lancer la génération pour la phase suivante (poules ou tableau)
    db_phase_suivante = db.query(models.Phase).filter(models.Phase.id == phase_suivante_id).first()
    
    if not db_phase_suivante:
        raise HTTPException(status_code=404, detail="Phase suivante non trouvée")
    
    nb_poules_creees = 0
    rencontres_creees = 0
    
    # Si la phase suivante est de type poule, générer les poules
    if db_phase_suivante.type_general == 'poule':
        config = db_phase_suivante.configuration or {}
        
        # Récupérer config décalages
        phase_suivante_rel = db.execute(
            models.phase_evenement.select().where(
                models.phase_evenement.c.phase_id == phase_suivante_id,
                models.phase_evenement.c.evenement_id == evenement_id
            )
        ).first()
        
        config_decalages = {}
        if phase_suivante_rel and phase_suivante_rel.config_qualification:
            config_decalages = phase_suivante_rel.config_qualification.get('decalages', {})
        
        joueurs_min = config.get('min_joueurs_poule', 3)
        joueurs_max = config.get('max_joueurs_poule', 8)
        joueurs_souhaite = config.get('ideal_joueurs_poule', 6)
        
        nb_joueurs = len(joueurs_qualifies)
        nb_poules = calcul_nombre_poules_helper(nb_joueurs, joueurs_min, joueurs_max, joueurs_souhaite)
        
        # Créer les poules
        poules = []
        for i in range(nb_poules):
            nom_poule = f"Poule {i + 1}"
            poule = models.Poule(
                id=str(uuid.uuid4()),
                phase_id=phase_suivante_id,
                evenement_id=evenement_id,
                nom=nom_poule,
                ordre=i + 1
            )
            db.add(poule)
            poules.append(poule)
            nb_poules_creees += 1
        
        db.commit()
        
        # Récupérer les inscriptions des joueurs qualifiés pour répartition
        inscriptions_qualifies = db.execute(
            models.phase_evenement_joueur.select().where(
                models.phase_evenement_joueur.c.phase_id == phase_suivante_id,
                models.phase_evenement_joueur.c.evenement_id == evenement_id
            ).order_by(models.phase_evenement_joueur.c.ordre_inscription)
        ).all()
        
        # Répartir en serpentin
        repartition = repartir_joueurs_serpentin_helper(list(inscriptions_qualifies), nb_poules, db=db, config_decalages=config_decalages)
        
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
        
        # Générer les rencontres par poule
        for poule in poules:
            joueurs_poule = db.execute(
                models.poule_joueur.select().where(
                    models.poule_joueur.c.poule_id == poule.id
                ).order_by(models.poule_joueur.c.ordre)
            ).all()
            
            joueur_ids = [j.joueur_id for j in joueurs_poule]
            
            for joueur1_id, joueur2_id in itertools.combinations(joueur_ids, 2):
                rencontre = models.Rencontre(
                    id=str(uuid.uuid4()),
                    phase_id=phase_suivante_id,
                    evenement_id=evenement_id,
                    participants=[joueur1_id, joueur2_id],
                    poule_id=poule.id
                )
                db.add(rencontre)
                rencontres_creees += 1
        
        db.commit()
    
    elif db_phase_suivante.type_general == 'elimination' or db_phase_suivante.type_general == 'tableau':
        # Gestion des tableaux d'élimination directe
        import math
        
        nb_joueurs = len(joueurs_qualifies)
        
        # Calculer la puissance de 2 supérieure ou égale au nombre de joueurs
        taille_tableau = 1
        while taille_tableau < nb_joueurs:
            taille_tableau *= 2
        
        # Calculer le nombre total de tours (log2 de la taille)
        nb_tours = int(math.log2(taille_tableau))
        
        # Créer un tableau avec les positions (1 à taille_tableau)
        # Les positions manquantes sont des "byes" (passages automatiques)
        positions_tableau = [None] * taille_tableau
        
        # Placer les joueurs qualifiés selon leur classement (1er = position 0, 2e = position 1, etc.)
        for idx, joueur in enumerate(joueurs_qualifies):
            positions_tableau[idx] = joueur
        
        # Créer les matchs du premier tour selon la formule : pos + pos_adverse = taille + 1
        # Appariements : 1 vs 8, 2 vs 7, 3 vs 6, 4 vs 5 (pour un tableau de 8)
        matchs_a_creer = []
        for position in range(taille_tableau // 2):
            position_haute = position  # 0, 1, 2, 3 (représente 1er, 2e, 3e, 4e)
            position_basse = taille_tableau - 1 - position  # 7, 6, 5, 4 (représente 8e, 7e, 6e, 5e)
            
            joueur_haut = positions_tableau[position_haute]
            joueur_bas = positions_tableau[position_basse]
            
            # Si les deux joueurs existent, créer le match
            if joueur_haut and joueur_bas:
                matchs_a_creer.append({
                    'position_match': position,  # Position dans le tour (0, 1, 2, 3...)
                    'joueur1': joueur_haut,
                    'joueur2': joueur_bas,
                    'type': 'match_normal'
                })
            elif joueur_haut and not joueur_bas:
                # Joueur haut a un bye (passe automatiquement au tour suivant)
                matchs_a_creer.append({
                    'position_match': position,
                    'joueur1': joueur_haut,
                    'joueur2': None,
                    'type': 'bye'
                })
            elif not joueur_haut and joueur_bas:
                # Joueur bas a un bye (passe automatiquement au tour suivant)
                matchs_a_creer.append({
                    'position_match': position,
                    'joueur1': None,
                    'joueur2': joueur_bas,
                    'type': 'bye'
                })
        
        # Créer TOUS les matchs de TOUS les tours
        nb_byes = 0
        joueurs_avec_bye = []  # Joueurs qualifiés d'office pour le tour 2
        
        # TOUR 1 : Créer les matchs avec les joueurs réels
        for match_info in matchs_a_creer:
            if match_info['type'] == 'match_normal':
                # Match normal entre deux joueurs
                rencontre = models.Rencontre(
                    id=str(uuid.uuid4()),
                    phase_id=phase_suivante_id,
                    evenement_id=evenement_id,
                    participants=[match_info['joueur1']['joueur_id'], match_info['joueur2']['joueur_id']],
                    poule_id=None,
                    tour=1,
                    position=match_info['position_match']
                )
                db.add(rencontre)
                rencontres_creees += 1
            else:
                # Bye : créer un match avec un seul participant et marquer comme qualifié
                joueur_qualifie = match_info['joueur1'] if match_info['joueur1'] else match_info['joueur2']
                if joueur_qualifie:
                    rencontre = models.Rencontre(
                        id=str(uuid.uuid4()),
                        phase_id=phase_suivante_id,
                        evenement_id=evenement_id,
                        participants=[joueur_qualifie['joueur_id']],  # Un seul participant
                        poule_id=None,
                        tour=1,
                        position=match_info['position_match']
                    )
                    db.add(rencontre)
                    rencontres_creees += 1
                    joueurs_avec_bye.append({
                        'joueur_id': joueur_qualifie['joueur_id'],
                        'position_tour1': match_info['position_match']
                    })
                    nb_byes += 1
        
        # TOURS 2 à N : Créer tous les matchs avec participants vides
        for tour_num in range(2, nb_tours + 1):
            nb_matchs_ce_tour = taille_tableau // (2 ** tour_num)
            
            for position in range(nb_matchs_ce_tour):
                # Créer un match vide (participants seront ajoutés lors de la saisie des résultats)
                rencontre = models.Rencontre(
                    id=str(uuid.uuid4()),
                    phase_id=phase_suivante_id,
                    evenement_id=evenement_id,
                    participants=[],  # Vide pour l'instant
                    poule_id=None,
                    tour=tour_num,
                    position=position
                )
                db.add(rencontre)
                rencontres_creees += 1
        
        db.commit()
        
        # Pré-remplir le tour 2 avec les joueurs ayant un bye
        if joueurs_avec_bye:
            for joueur_bye in joueurs_avec_bye:
                # Trouver le match du tour 2 correspondant
                position_tour2 = joueur_bye['position_tour1'] // 2
                match_tour2 = db.query(models.Rencontre).filter(
                    models.Rencontre.phase_id == phase_suivante_id,
                    models.Rencontre.tour == 2,
                    models.Rencontre.position == position_tour2
                ).first()
                
                if match_tour2:
                    # Ajouter le joueur dans le match du tour 2
                    if not match_tour2.participants:
                        match_tour2.participants = []
                    match_tour2.participants.append(joueur_bye['joueur_id'])
                    db.add(match_tour2)
            
            db.commit()
        
        return {
            "message": "Progression vers la phase suivante réussie (tableau d'élimination complet créé)",
            "phase_precedente_id": phase_id,
            "phase_suivante_id": phase_suivante_id,
            "joueurs_qualifies": len(joueurs_qualifies),
            "taille_tableau": taille_tableau,
            "nb_tours": nb_tours,
            "nb_byes": nb_byes,
            "rencontres_creees": rencontres_creees,
            "info": f"Tableau de {taille_tableau} ({nb_tours} tours) : {rencontres_creees} match(s) créé(s) pour tous les tours, {nb_byes} bye(s)"
        }
    
    return {
        "message": "Progression vers la phase suivante réussie",
        "phase_precedente_id": phase_id,
        "phase_suivante_id": phase_suivante_id,
        "joueurs_qualifies": len(joueurs_qualifies),
        "nb_poules_creees": nb_poules_creees,
        "rencontres_creees": rencontres_creees
    }

def calculer_classement_poule_helper(poule_id: str, phase_id: str, evenement_id: str, db: Session):
    """Calcule le classement d'une poule"""
    # Récupérer les joueurs de la poule
    joueurs_poule = db.execute(
        models.poule_joueur.select().where(
            models.poule_joueur.c.poule_id == poule_id
        )
    ).all()
    
    # Initialiser les stats
    stats = {}
    for joueur in joueurs_poule:
        stats[joueur.joueur_id] = {
            'joueur_id': joueur.joueur_id,
            'victoires': 0,
            'defaites': 0,
            'nuls': 0,
            'points': 0
        }
    
    # Récupérer les rencontres de la poule
    rencontres = db.query(models.Rencontre).filter(
        models.Rencontre.poule_id == poule_id,
        models.Rencontre.phase_id == phase_id,
        models.Rencontre.evenement_id == evenement_id
    ).all()
    
    # Calculer les stats
    for rencontre in rencontres:
        resultats = db.query(models.Resultat).filter(
            models.Resultat.rencontre_id == rencontre.id
        ).all()
        
        if not resultats or len(resultats) < 2:
            continue
        
        # Supposer que le premier résultat est le gagnant (ou égalité si même classement)
        resultats_sorted = sorted(resultats, key=lambda r: r.classement if r.classement else 999)
        
        if len(resultats_sorted) >= 2:
            if resultats_sorted[0].classement == resultats_sorted[1].classement:
                # Égalité
                for res in resultats_sorted:
                    if res.participant_id in stats:
                        stats[res.participant_id]['nuls'] += 1
                        stats[res.participant_id]['points'] += 1
            else:
                # Victoire/défaite
                gagnant_id = resultats_sorted[0].participant_id
                if gagnant_id in stats:
                    stats[gagnant_id]['victoires'] += 1
                    stats[gagnant_id]['points'] += 3
                
                for res in resultats_sorted[1:]:
                    if res.participant_id in stats:
                        stats[res.participant_id]['defaites'] += 1
    
    # Trier par points décroissants, puis victoires
    classement = sorted(stats.values(), key=lambda x: (-x['points'], -x['victoires']))
    
    return classement

def calculer_classement_phase_helper(phase_id: str, evenement_id: str, db: Session):
    """Calcule le classement général d'une phase"""
    # Récupérer tous les joueurs de la phase
    joueurs_phase = db.execute(
        models.phase_evenement_joueur.select().where(
            models.phase_evenement_joueur.c.phase_id == phase_id,
            models.phase_evenement_joueur.c.evenement_id == evenement_id
        )
    ).all()
    
    # Initialiser les stats
    stats = {}
    for joueur in joueurs_phase:
        stats[joueur.joueur_id] = {
            'joueur_id': joueur.joueur_id,
            'victoires': 0,
            'defaites': 0,
            'nuls': 0,
            'points': 0
        }
    
    # Récupérer toutes les rencontres de la phase
    rencontres = db.query(models.Rencontre).filter(
        models.Rencontre.phase_id == phase_id,
        models.Rencontre.evenement_id == evenement_id
    ).all()
    
    # Calculer les stats (même logique que pour les poules)
    for rencontre in rencontres:
        resultats = db.query(models.Resultat).filter(
            models.Resultat.rencontre_id == rencontre.id
        ).all()
        
        if not resultats or len(resultats) < 2:
            continue
        
        resultats_sorted = sorted(resultats, key=lambda r: r.classement if r.classement else 999)
        
        if len(resultats_sorted) >= 2:
            if resultats_sorted[0].classement == resultats_sorted[1].classement:
                for res in resultats_sorted:
                    if res.participant_id in stats:
                        stats[res.participant_id]['nuls'] += 1
                        stats[res.participant_id]['points'] += 1
            else:
                gagnant_id = resultats_sorted[0].participant_id
                if gagnant_id in stats:
                    stats[gagnant_id]['victoires'] += 1
                    stats[gagnant_id]['points'] += 3
                
                for res in resultats_sorted[1:]:
                    if res.participant_id in stats:
                        stats[res.participant_id]['defaites'] += 1
    
    # Trier par points décroissants, puis victoires
    classement = sorted(stats.values(), key=lambda x: (-x['points'], -x['victoires']))
    
    return classement

@router.post("/evenements/{evenement_id}/phases/{phase_id}/tableau/generate-next-round")
def generate_next_round(evenement_id: str, phase_id: str, current_tour: int, db: Session = Depends(get_db)):
    """Générer automatiquement le tour suivant du tableau d'élimination"""
    import math
    
    # Vérifier que la phase existe et est de type tableau
    phase = db.query(models.Phase).filter(models.Phase.id == phase_id).first()
    if not phase:
        raise HTTPException(status_code=404, detail="Phase non trouvée")
    
    if phase.type_general not in ['elimination', 'tableau']:
        raise HTTPException(status_code=400, detail="Cette phase n'est pas un tableau d'élimination")
    
    # Récupérer toutes les rencontres du tour actuel
    rencontres_tour = db.query(models.Rencontre).filter(
        models.Rencontre.phase_id == phase_id,
        models.Rencontre.tour == current_tour
    ).all()
    
    if not rencontres_tour:
        raise HTTPException(status_code=404, detail=f"Aucune rencontre trouvée pour le tour {current_tour}")
    
    # Vérifier que toutes les rencontres du tour sont terminées
    gagnants = []
    for rencontre in rencontres_tour:
        resultats = db.query(models.Resultat).filter(
            models.Resultat.rencontre_id == rencontre.id
        ).all()
        
        if not resultats:
            raise HTTPException(
                status_code=400, 
                detail=f"Le tour {current_tour} n'est pas terminé (match {rencontre.id} sans résultat)"
            )
        
        # Trouver le gagnant (classement = 1)
        gagnant = next((r for r in resultats if r.classement == 1), None)
        if not gagnant:
            raise HTTPException(
                status_code=400,
                detail=f"Pas de gagnant trouvé pour le match {rencontre.id}"
            )
        
        gagnants.append({
            'joueur_id': gagnant.participant_id,
            'position_precedente': rencontre.position
        })
    
    # Trier les gagnants par position
    gagnants.sort(key=lambda x: x['position_precedente'])
    
    # Créer les rencontres du tour suivant
    tour_suivant = current_tour + 1
    nb_matchs_suivants = len(gagnants) // 2
    rencontres_creees = 0
    
    for i in range(nb_matchs_suivants):
        joueur1_id = gagnants[i * 2]['joueur_id']
        joueur2_id = gagnants[i * 2 + 1]['joueur_id']
        
        nouvelle_rencontre = models.Rencontre(
            phase_id=phase_id,
            participants=[joueur1_id, joueur2_id],
            tour=tour_suivant,
            position=i
        )
        db.add(nouvelle_rencontre)
        rencontres_creees += 1
    
    db.commit()
    
    return {
        "message": f"Tour {tour_suivant} généré avec succès",
        "tour_precedent": current_tour,
        "tour_suivant": tour_suivant,
        "nb_gagnants": len(gagnants),
        "rencontres_creees": rencontres_creees
    } 