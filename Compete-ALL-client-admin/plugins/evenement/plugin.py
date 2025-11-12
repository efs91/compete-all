# Plugin de démonstration pour les événements
print("Plugin Evenement chargé!")

# Ce fichier est juste une démonstration
# Dans une version complète, il contiendrait la logique du plugin
# comme les routes, les modèles, etc.

def initialize():
    """Initialiser le plugin"""
    print("Plugin Evenement initialisé!")
    return True

def get_info():
    """Obtenir des informations sur le plugin"""
    return {
        "name": "evenement",
        "version": "0.1.0",
        "description": "Plugin de gestion des événements pour Compete-All",
        "routes": [
            {
                "path": "/evenements", 
                "description": "Liste des événements",
                "name": "Événements",
                "endpoint": "list_evenements"
            },
            {
                "path": "/evenements/nouveau",
                "description": "Créer un événement",
                "name": "Nouvel événement",
                "endpoint": "add_evenement"
            },
            {
                "path": "/evenements/<evenement_id>",
                "description": "Détails d'un événement",
                "name": "Détails de l'événement",
                "endpoint": "view_evenement",
                "hidden": True  # Ne pas afficher dans le menu principal
            },
            {
                "path": "/evenements/<evenement_id>/edit",
                "description": "Modifier un événement",
                "name": "Modifier l'événement",
                "endpoint": "edit_evenement",
                "hidden": True  # Ne pas afficher dans le menu principal
            }
        ]
    } 