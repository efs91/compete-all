from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

class EvenementBase(BaseModel):
    nom: str
    date_debut: datetime
    date_fin: datetime
    description: Optional[str] = None
    statut: Optional[str] = 'brouillon'

class EvenementCreate(EvenementBase):
    pass

class Evenement(EvenementBase):
    id: str
    class Config:
        from_attributes = True

class FormatBase(BaseModel):
    nom: str
    proprietes: Optional[Dict[str, Any]] = None

class FormatCreate(FormatBase):
    pass

class Format(FormatBase):
    id: str
    class Config:
        from_attributes = True

class TypeBase(BaseModel):
    nom: str
    proprietes: Optional[Dict[str, Any]] = None
    resultats_config: Optional[Dict[str, bool]] = None  # Ex: {"classement": true, "points": true, "actions": false}

class TypeCreate(TypeBase):
    pass

class Type(TypeBase):
    id: str
    class Config:
        from_attributes = True

class UserIngame(BaseModel):
    game: str
    id: str

class Classement(BaseModel):
    type: str
    place: str

class JoueurBase(BaseModel):
    username: str
    prenom: Optional[str] = None
    nom: Optional[str] = None
    email: Optional[str] = None
    date_naissance: Optional[datetime] = None
    telephone: Optional[str] = None
    users_ingame: Optional[List[Dict[str, str]]] = None  # [{"epic_game": "id", "steam": "id"}]
    user_discord: Optional[str] = None
    classements: Optional[List[Dict[str, str]]] = None  # [{"National": "17", "International": "44"}]
    nation: Optional[str] = None
    club: Optional[str] = None
    status: Optional[str] = None
    comment: Optional[str] = None
    photos: Optional[List[str]] = None  # Liste d'URLs de photos

class JoueurCreate(JoueurBase):
    pass

class JoueurSimple(JoueurBase):
    id: str
    class Config:
        from_attributes = True

# Définition de PhaseSimple avant JoueurDetail qui l'utilise
class PhaseSimple(BaseModel):
    id: str
    nom: str
    type_general: Optional[str] = None
    format_id: str
    type_id: str
    ordre: Optional[int] = None
    description: Optional[str] = None
    scoring: Optional[Dict[str, Any]] = None
    configuration: Optional[Dict[str, Any]] = None
    class Config:
        from_attributes = True

class JoueurDetail(JoueurBase):
    id: str
    phases: List[PhaseSimple] = []
    class Config:
        from_attributes = True

# Phases
class PhaseEvenementJoueurBase(BaseModel):
    joueur_id: str
    phase_id: str
    evenement_id: str
    ordre_inscription: int
    seed: Optional[int] = None

class PhaseEvenementJoueurCreate(BaseModel):
    joueur_id: str
    ordre_inscription: int = 0
    seed: Optional[int] = None

class PhaseEvenementJoueurDetail(PhaseEvenementJoueurBase):
    joueur: JoueurSimple
    class Config:
        from_attributes = True

class PhaseBase(BaseModel):
    nom: str
    type_general: Optional[str] = None
    format_id: str
    type_id: str
    ordre: Optional[int] = None
    description: Optional[str] = None
    scoring: Optional[Dict[str, Any]] = None
    configuration: Optional[Dict[str, Any]] = None

class PhaseCreate(PhaseBase):
    pass

# Événement
class EvenementSimple(EvenementBase):
    id: str
    class Config:
        from_attributes = True

# Relations Phase-Événement
class PhaseEventRelation(BaseModel):
    phase_id: str
    evenement_id: str
    joueurs: Optional[List[PhaseEvenementJoueurCreate]] = None
    config_qualification: Optional[dict] = None  # Configuration de qualification
    config_decalages: Optional[dict] = None  # Configuration des décalages de poules

class PhaseInEvent(PhaseBase):
    id: str
    format: Format
    type: Type
    joueurs: List[PhaseEvenementJoueurDetail] = []
    class Config:
        from_attributes = True

class EventWithPhases(EvenementBase):
    id: str
    phases: List[PhaseSimple] = []
    class Config:
        from_attributes = True

# équipes
class EquipeBase(BaseModel):
    nom: str
    membres: List[str]  # Liste d'IDs de joueurs

class EquipeCreate(EquipeBase):
    evenement_id: Optional[str] = None

class Equipe(EquipeBase):
    id: str
    evenement_id: Optional[str] = None
    class Config:
        from_attributes = True

# Rencontres
class RencontreBase(BaseModel):
    participants: Optional[List[str]] = None  # Liste des IDs des participants
    tour: Optional[int] = 1  # Numéro du tour dans le bracket
    position: Optional[int] = 0  # Position du match dans le tour

class RencontreCreate(RencontreBase):
    evenement_id: str

class Rencontre(RencontreBase):
    id: str
    phase_id: str
    evenement_id: Optional[str] = None
    class Config:
        from_attributes = True

# Résultats
class ResultatBase(BaseModel):
    participant_id: str
    classement: Optional[int] = None
    points: Optional[int] = None
    actions: Optional[Dict[str, Any]] = None

class ResultatCreate(ResultatBase):
    pass

class Resultat(ResultatBase):
    id: str
    rencontre_id: str
    class Config:
        from_attributes = True

# Règles
class RegleBase(BaseModel):
    nom: str
    description: Optional[str] = None
    valeurs: Dict[str, Any]

class RegleCreate(RegleBase):
    pass

class Regle(RegleBase):
    id: str
    class Config:
        from_attributes = True

# Classements
class ClassementBase(BaseModel):
    nom: str
    evenement_id: Optional[str] = None
    phase_id: Optional[str] = None
    rencontre_id: Optional[str] = None
    regle_id: Optional[str] = None
    points: Dict[str, Any]

class ClassementCreate(ClassementBase):
    pass

class Classement(ClassementBase):
    id: str
    class Config:
        from_attributes = True 