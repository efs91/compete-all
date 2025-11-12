# Plugin de gestion des phases pour Compete-All
print("Plugin Phase chargé!")

# Ce fichier contient la définition des routes et fonctionnalités du plugin des phases

def initialize():
    """Initialiser le plugin"""
    print("Plugin Phase initialisé!")
    return True

def get_info():
    """Obtenir des informations sur le plugin"""
    return {
        "name": "phase",
        "version": "0.1.0",
        "description": "Plugin de gestion des phases pour Compete-All",
        "routes": [
            {
                "path": "/phases", 
                "description": "Gestion des templates de phases",
                "name": "Templates de phases",
                "endpoint": "list_phases"
            },
            {
                "path": "/phases/nouveau",
                "description": "Créer un template de phase",
                "name": "Nouveau template",
                "endpoint": "add_phase"
            },
            {
                "path": "/evenements/phases",
                "description": "Gestion des phases par événement",
                "name": "Phases par événement",
                "endpoint": "list_event_phases"
            },
            {
                "path": "/phases/<phase_id>",
                "description": "Détails d'un template de phase",
                "name": "Détails du template",
                "endpoint": "view_phase",
                "hidden": True
            },
            {
                "path": "/phases/<phase_id>/edit",
                "description": "Modifier un template de phase",
                "name": "Modifier le template",
                "endpoint": "edit_phase",
                "hidden": True
            },
            {
                "path": "/evenements/<evenement_id>/phases",
                "description": "Phases d'un événement spécifique",
                "name": "Phases de l'événement",
                "endpoint": "view_event_phases",
                "hidden": True
            },
            {
                "path": "/evenements/<evenement_id>/phases/<phase_id>/joueurs",
                "description": "Joueurs d'une phase",
                "name": "Joueurs de la phase",
                "endpoint": "view_phase_players",
                "hidden": True
            }
        ]
    } 