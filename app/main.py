from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from . import models
from .database import engine, check_and_update_schema

# Vérifier et mettre à jour le schéma de la base de données si nécessaire
check_and_update_schema()

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Compete-All API",
    description="API pour la gestion de compétitions sportives et ludiques",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Autorise toutes les origines en développement
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],  # Autorise tous les en-têtes en développement
)

# Monter le dossier static pour les photos des joueurs
STATIC_DIR = os.path.join("app", "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API Compete-All"}

# Point de montage pour les routes
from .routers import (
    evenements,
    phases,
    rencontres,
    joueurs,
    equipes,
    resultats,
    regles,
    classements,
    formats,
    types,
    poules
)

app.include_router(evenements.router, prefix="/evenements", tags=["evenements"])
app.include_router(phases.router, tags=["phases"])
app.include_router(poules.router, tags=["poules"])
app.include_router(rencontres.router, tags=["rencontres"])
app.include_router(joueurs.router, prefix="/joueurs", tags=["joueurs"])
app.include_router(equipes.router, prefix="/equipes", tags=["equipes"])
app.include_router(resultats.router, tags=["resultats"])
app.include_router(regles.router, prefix="/regles", tags=["regles"])
app.include_router(classements.router, prefix="/classements", tags=["classements"])
app.include_router(formats.router, tags=["formats"])
app.include_router(types.router, tags=["types"]) 