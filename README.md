# Compete-All API

API de gestion de compétitions sportives et ludiques - Version Carabaffe

## Description

Cette API permet de gérer tout type de compétition sportive ou ludique : championnats, tournois, événements ponctuels, poules, tableaux à élimination directe, compétitions individuelles ou par équipe.

## Prérequis

- Python 3.8+
- MySQL

## Installation

1. Cloner le repository :
```bash
git clone [URL_DU_REPO]
cd compete-all
```

2. Créer un environnement virtuel et l'activer :
```bash
python -m venv venv
source venv/bin/activate  # Sur Linux/Mac
# ou
.\venv\Scripts\activate  # Sur Windows
```

3. Installer les dépendances :
```bash
pip install -r requirements.txt
```

4. Créer un fichier `.env` à la racine du projet avec les informations de connexion à la base de données :
```
DB_HOST=efs91.fr
DB_USER=carabaffe
DB_PASSWORD=sbirneb91
DB_NAME=carabaffe
DB_PORT=3306
```

## Démarrage

Pour démarrer l'API en mode développement :

```bash
uvicorn app.main:app --reload
```

L'API sera accessible à l'adresse : http://localhost:8000

La documentation Swagger sera disponible à : http://localhost:8000/docs

## Structure du Projet

```
compete-all/
├── app/
│   ├── routers/
│   │   ├── evenements.py
│   │   ├── phases.py
│   │   ├── rencontres.py
│   │   └── ...
│   ├── __init__.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── .env
├── README.md
└── requirements.txt
```

## Endpoints API

- `/evenements` : Gestion des événements
- `/phases` : Gestion des phases de compétition
- `/rencontres` : Gestion des rencontres
- `/participants` : Gestion des participants
- `/joueurs` : Gestion des joueurs
- `/equipes` : Gestion des équipes
- `/resultats` : Gestion des résultats
- `/regles` : Gestion des règles personnalisées

Pour plus de détails sur les endpoints, consultez la documentation Swagger à l'adresse : http://localhost:8000/docs 