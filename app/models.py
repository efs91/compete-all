from sqlalchemy import Column, String, Integer, ForeignKey, Table, JSON, DateTime
from sqlalchemy.orm import relationship
from .database import Base
import uuid
from datetime import datetime

# Tables d'association
equipe_joueur = Table(
    'equipe_joueur', 
    Base.metadata,
    Column('equipe_id', String(36), ForeignKey('equipes.id')),
    Column('joueur_id', String(36), ForeignKey('joueurs.id'))
)

# Suppression de la table phase_joueur qui sera remplacée par phase_evenement_joueur
# phase_joueur = Table(
#     'phase_joueur', 
#     Base.metadata,
#     Column('phase_id', String(36), ForeignKey('phases.id')),
#     Column('joueur_id', String(36), ForeignKey('joueurs.id')),
#     Column('ordre_inscription', Integer, nullable=False),
#     Column('seed', Integer, nullable=True)
# )

# Nouvelle table de liaison à trois voies: phase-evenement-joueur
phase_evenement_joueur = Table(
    'phase_evenement_joueur', 
    Base.metadata,
    Column('phase_id', String(36), ForeignKey('phases.id')),
    Column('evenement_id', String(36), ForeignKey('evenements.id')),
    Column('joueur_id', String(36), ForeignKey('joueurs.id')),
    Column('ordre_inscription', Integer, nullable=False),
    Column('seed', Integer, nullable=True)
)

# Table de liaison entre phases et événements
phase_evenement = Table(
    'phase_evenement',
    Base.metadata,
    Column('phase_id', String(36), ForeignKey('phases.id')),
    Column('evenement_id', String(36), ForeignKey('evenements.id'))
)

class Format(Base):
    __tablename__ = "formats"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nom = Column(String(50), nullable=False, unique=True)
    proprietes = Column(JSON, nullable=True)
    
    phases = relationship("Phase", back_populates="format")

class Type(Base):
    __tablename__ = "types"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nom = Column(String(50), nullable=False, unique=True)
    proprietes = Column(JSON, nullable=True)
    resultats_config = Column(JSON, nullable=True)  # Config des champs de résultats: {classement: bool, points: bool, actions: bool}
    
    phases = relationship("Phase", back_populates="type")

class Joueur(Base):
    __tablename__ = "joueurs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(255), nullable=False, unique=True)
    prenom = Column(String(255), nullable=True)
    nom = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    date_naissance = Column(DateTime, nullable=True)
    telephone = Column(String(20), nullable=True)
    users_ingame = Column(JSON, nullable=True)  # Pour stocker le tableau d'identifiants de jeux
    user_discord = Column(String(255), nullable=True)
    classements = Column(JSON, nullable=True)  # Pour stocker le tableau de classements
    nation = Column(String(255), nullable=True)
    club = Column(String(255), nullable=True)
    status = Column(String(255), nullable=True)
    comment = Column(String(1000), nullable=True)
    photos = Column(JSON, nullable=True)  # Pour stocker un tableau d'URLs de photos

    equipes = relationship("Equipe", secondary=equipe_joueur, back_populates="joueurs")
    # Modification de la relation pour utiliser la nouvelle table de liaison
    phases = relationship("Phase", secondary=phase_evenement_joueur, back_populates="joueurs")
    evenements = relationship("Evenement", secondary=phase_evenement_joueur, back_populates="joueurs")

class Phase(Base):
    __tablename__ = "phases"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nom = Column(String(255), nullable=False)
    format_id = Column(String(36), ForeignKey("formats.id"), nullable=False)
    type_id = Column(String(36), ForeignKey("types.id"), nullable=False)
    scoring = Column(JSON, nullable=True)
    configuration = Column(JSON, nullable=False)
    # Suppression de evenement_id car une phase peut être dans plusieurs événements
    # evenement_id = Column(String(36), ForeignKey("evenements.id"))
    
    # Modification des relations
    # evenement = relationship("Evenement", back_populates="phases")
    evenements = relationship("Evenement", secondary=phase_evenement, back_populates="phases")
    format = relationship("Format", back_populates="phases")
    type = relationship("Type", back_populates="phases")
    # Utilisation de la nouvelle table de liaison
    joueurs = relationship("Joueur", secondary=phase_evenement_joueur, back_populates="phases")
    rencontres = relationship("Rencontre", back_populates="phase")
    classements = relationship("Classement", back_populates="phase")

class Equipe(Base):
    __tablename__ = "equipes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nom = Column(String(255), nullable=False)
    evenement_id = Column(String(36), ForeignKey("evenements.id"), nullable=True)
    
    evenement = relationship("Evenement", back_populates="equipes")
    joueurs = relationship("Joueur", secondary=equipe_joueur, back_populates="equipes")

class Evenement(Base):
    __tablename__ = "evenements"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nom = Column(String(255), nullable=False)
    date_debut = Column(DateTime, nullable=False)
    date_fin = Column(DateTime, nullable=False)
    description = Column(String(1000), nullable=True)
    
    # Mise à jour des relations
    phases = relationship("Phase", secondary=phase_evenement, back_populates="evenements")
    joueurs = relationship("Joueur", secondary=phase_evenement_joueur, back_populates="evenements")
    equipes = relationship("Equipe", back_populates="evenement")
    classements = relationship("Classement", back_populates="evenement")

class Rencontre(Base):
    __tablename__ = "rencontres"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phase_id = Column(String(36), ForeignKey("phases.id"), nullable=False)
    evenement_id = Column(String(36), ForeignKey("evenements.id"), nullable=False)  # Ajout de l'événement
    participants = Column(JSON, nullable=True)  # Liste des IDs des participants ["joueur_id1", "joueur_id2", ...]
    
    phase = relationship("Phase", back_populates="rencontres")
    evenement = relationship("Evenement")  # Ajout de la relation avec l'événement
    resultats = relationship("Resultat", back_populates="rencontre")
    classements = relationship("Classement", back_populates="rencontre")

class Resultat(Base):
    __tablename__ = "resultats"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rencontre_id = Column(String(36), ForeignKey("rencontres.id"), nullable=False)
    participant_id = Column(String(36), nullable=False)  # ID d'un joueur ou d'une équipe
    classement = Column(Integer, nullable=True)  # Position/rang dans la rencontre (optionnel)
    points = Column(Integer, nullable=True)  # Points obtenus (optionnel)
    actions = Column(JSON, nullable=True)  # Actions/détails supplémentaires (optionnel)
    
    rencontre = relationship("Rencontre", back_populates="resultats")
    # La relation avec participant est supprimée car nous utilisons directement joueur ou equipe

class Regle(Base):
    __tablename__ = "regles"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nom = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    valeurs = Column(JSON, nullable=False)
    
    classement = relationship("Classement", back_populates="regle")

class Classement(Base):
    __tablename__ = "classements"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nom = Column(String(255), nullable=False)
    evenement_id = Column(String(36), ForeignKey("evenements.id"), nullable=True)
    phase_id = Column(String(36), ForeignKey("phases.id"), nullable=True)
    rencontre_id = Column(String(36), ForeignKey("rencontres.id"), nullable=True)
    regle_id = Column(String(36), ForeignKey("regles.id"), nullable=True)
    points = Column(JSON, nullable=False)  # {joueur_id: points, ...}
    
    evenement = relationship("Evenement", back_populates="classements")
    phase = relationship("Phase", back_populates="classements")
    rencontre = relationship("Rencontre", back_populates="classements")
    regle = relationship("Regle", back_populates="classement") 