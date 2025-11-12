# Compete-All Python

Une application web Python simple pour gérer des compétitions via l'API Compete-All.

## Présentation

**Compete-All Python** est une interface utilisateur simple pour l'API Compete-All qui permet de :
- Gérer les utilisateurs (création, modification, suppression)
- Gérer les plugins modulaires

## Installation

l'API est dans /dev/cursor

1. Cloner ce dépôt
```bash
git clone <url-du-repo>
cd Compete-ALL
```

2. Créer un environnement Conda et l'activer
```bash
# Créer l'environnement
conda create -n compete-all python=3.10

# Activer l'environnement
# Windows
conda activate compete-all

# Linux/Mac
conda activate compete-all
```

3. Installer les dépendances
```bash
pip install -r requirements.txt
```

## Utilisation

1. Lancer l'application
```bash
python app.py
```

2. Ouvrir un navigateur et accéder à http://localhost:5000

## Structure du projet

```
Compete-ALL/
├── app.py                  # Application principale
├── templates/              # Templates HTML
│   ├── base.html           # Template de base
│   ├── index.html          # Page d'accueil
│   ├── users/              # Templates pour les utilisateurs
│   └── plugins/            # Templates pour les plugins
├── plugins/                # Dossier des plugins modulaires
│   └── evenement/          # Exemple de plugin
│       ├── manifest.json   # Métadonnées du plugin
│       └── plugin.py       # Code du plugin
├── requirements.txt        # Dépendances Python
└── README.md               # Documentation
```

## Développement de plugins

Pour créer un nouveau plugin :

1. Créez un nouveau dossier dans `plugins/`
2. Ajoutez un fichier `manifest.json` avec les métadonnées du plugin
3. Ajoutez un fichier Python principal (défini dans manifest.json)

Exemple de `manifest.json` :
```json
{
  "name": "mon-plugin",
  "version": "0.1.0",
  "description": "Description de mon plugin",
  "main": "plugin.py",
  "dependencies": []
}
```

## API

L'application utilise l'API Compete-All existante à l'adresse :
https://benribs.fr/compete-all/ 