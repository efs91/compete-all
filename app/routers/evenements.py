from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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
    
    # 6. Supprimer les équipes de l'événement
    db.query(models.Equipe).filter(
        models.Equipe.evenement_id == evenement_id
    ).delete(synchronize_session=False)
    
    # 7. Supprimer les inscriptions joueurs (phase_evenement_joueur)
    db.execute(
        models.phase_evenement_joueur.delete().where(
            models.phase_evenement_joueur.c.evenement_id == evenement_id
        )
    )
    
    # 8. Supprimer les relations phases-événement
    db.execute(
        models.phase_evenement.delete().where(
            models.phase_evenement.c.evenement_id == evenement_id
        )
    )
    
    # 9. Enfin, supprimer l'événement lui-même
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
    
    # Récupérer la première phase (ordre = 1)
    premiere_phase = db.execute(
        models.phase_evenement.select().where(
            models.phase_evenement.c.evenement_id == evenement_id,
            models.phase_evenement.c.ordre == 1
        )
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
    
    # Répartir les joueurs en serpentin avec décalages intelligents (éviter même club/nation)
    joueurs_phase = list(inscriptions)
    repartition = repartir_joueurs_serpentin_helper(joueurs_phase, nb_poules, db=db)
    
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
    
    return {
        "message": "Compétition lancée avec succès",
        "phase_id": phase_id,
        "joueurs_inscrits": joueurs_inscrits,
        "total_joueurs": len(inscriptions),
        "nb_poules": nb_poules,
        "rencontres_creees": rencontres_creees
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

def repartir_joueurs_serpentin_helper(joueurs_inscrits: List, nb_poules: int, db: Session = None) -> List[List]:
    """
    Répartit les joueurs en serpentin avec décalages intelligents.
    Évite de mettre des joueurs du même club ou de la même nation dans la même poule.
    """
    from collections import defaultdict
    
    poules = [[] for _ in range(nb_poules)]
    
    # Si pas de DB fournie, faire la répartition simple en serpentin
    if db is None:
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
        Retourne le nombre de joueurs avec le même club + nombre avec la même nation.
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
            
            # Conflit de club (poids 2)
            if nouveau_joueur.club and joueur.club and nouveau_joueur.club.strip().lower() == joueur.club.strip().lower():
                conflits += 2
            
            # Conflit de nation (poids 1)
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