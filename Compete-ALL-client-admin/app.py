from flask import Flask, render_template, request, redirect, url_for, flash
import requests
import os
import json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "compete-all-secret-key"  # Utilisé pour les messages flash

# Configuration de l'API
API_BASE_URL = "https://benribs.fr/compete-all"
PLUGINS_DIR = "plugins"
PLUGINS_STATE_FILE = "plugins_state.json"

# Assurez-vous que le dossier des plugins existe
os.makedirs(PLUGINS_DIR, exist_ok=True)

# Liste des plugins actifs
active_plugins = []

# Charger l'état des plugins depuis le fichier
def load_plugins_state():
    """Charge la liste des plugins activés depuis le fichier JSON"""
    global active_plugins
    if os.path.exists(PLUGINS_STATE_FILE):
        try:
            with open(PLUGINS_STATE_FILE, 'r') as f:
                state = json.load(f)
                active_plugins = state.get('active_plugins', [])
                print(f"Plugins activés chargés : {active_plugins}")
        except Exception as e:
            print(f"Erreur lors du chargement de l'état des plugins : {e}")
            active_plugins = []
    else:
        active_plugins = []

def save_plugins_state():
    """Sauvegarde la liste des plugins activés dans le fichier JSON"""
    try:
        with open(PLUGINS_STATE_FILE, 'w') as f:
            json.dump({'active_plugins': active_plugins}, f, indent=2)
        print(f"État des plugins sauvegardé : {active_plugins}")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde de l'état des plugins : {e}")

# Initialiser les plugins actifs
def initialize_active_plugins():
    plugins = load_plugins()
    for plugin in plugins:
        if plugin['active']:
            plugin_name = plugin['name']
            plugin_dir = Path(plugin['path'])
            plugin_file = plugin_dir / "plugin.py"
            
            if plugin_file.exists():
                plugin_module_path = f"{PLUGINS_DIR}.{plugin_dir.name}.plugin"
                try:
                    plugin_module = __import__(plugin_module_path, fromlist=['initialize'])
                    if hasattr(plugin_module, 'initialize'):
                        plugin_module.initialize()
                        print(f"Plugin {plugin_name} initialisé avec succès!")
                except Exception as e:
                    print(f"Erreur lors de l'initialisation du plugin {plugin_name}: {e}")

# Charger les plugins disponibles
def load_plugins():
    plugins = []
    plugin_dirs = [f for f in Path(PLUGINS_DIR).iterdir() if f.is_dir()]
    
    for plugin_dir in plugin_dirs:
        manifest_path = plugin_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    plugin_info = {
                        "name": manifest.get("name", "Unknown"),
                        "version": manifest.get("version", "0.0.0"),
                        "description": manifest.get("description", ""),
                        "path": str(plugin_dir),
                        "active": manifest.get("name") in active_plugins
                    }
                    
                    # Si le plugin a un fichier plugin.py, charger les informations supplémentaires
                    plugin_file = plugin_dir / "plugin.py"
                    if plugin_file.exists():
                        # Essayer d'importer le plugin et d'obtenir ses informations
                        plugin_module_path = f"{PLUGINS_DIR}.{plugin_dir.name}.plugin"
                        try:
                            plugin_module = __import__(plugin_module_path, fromlist=['get_info'])
                            if hasattr(plugin_module, 'get_info'):
                                plugin_extra_info = plugin_module.get_info()
                                # Fusionner les informations supplémentaires
                                if 'routes' in plugin_extra_info:
                                    plugin_info['routes'] = plugin_extra_info['routes']
                        except Exception as e:
                            print(f"Erreur lors du chargement du module {plugin_module_path}: {e}")
                    
                    plugins.append(plugin_info)
            except Exception as e:
                print(f"Erreur lors du chargement du plugin {plugin_dir.name}: {e}")
                
    return plugins

# Fonction pour obtenir les plugins actifs avec leurs routes
def get_active_plugins_routes():
    plugins = load_plugins()
    active_plugins_with_routes = []
    
    for plugin in plugins:
        if plugin['active'] and 'routes' in plugin:
            active_plugins_with_routes.append(plugin)
    
    return active_plugins_with_routes

# Ajouter les informations des plugins actifs à chaque requête
@app.context_processor
def inject_active_plugins():
    return {'active_plugins_routes': get_active_plugins_routes()}

# Routes principales
@app.route('/')
def index():
    return render_template('index.html')

# Gestion des utilisateurs
@app.route('/users')
def list_users():
    try:
        response = requests.get(f"{API_BASE_URL}/joueurs")
        if response.status_code == 200:
            users = response.json()
            return render_template('users/list.html', users=users)
        else:
            flash(f"Erreur lors de la récupération des utilisateurs: {response.status_code}", "error")
            return render_template('users/list.html', users=[])
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return render_template('users/list.html', users=[])

@app.route('/users/<user_id>')
def view_user(user_id):
    try:
        response = requests.get(f"{API_BASE_URL}/joueurs/{user_id}")
        if response.status_code == 200:
            user = response.json()
            return render_template('users/view.html', user=user)
        else:
            flash(f"Utilisateur non trouvé: {response.status_code}", "error")
            return redirect(url_for('list_users'))
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('list_users'))

@app.route('/users/new', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        user_data = {
            "username": request.form.get('username'),
            "prenom": request.form.get('prenom') or None,
            "nom": request.form.get('nom') or None,
            "email": request.form.get('email') or None,
            "telephone": request.form.get('telephone') or None,
            "nation": request.form.get('nation') or None,
            "club": request.form.get('club') or None
        }
        
        try:
            response = requests.post(f"{API_BASE_URL}/joueurs", json=user_data)
            if response.status_code in (200, 201):
                new_user = response.json()
                user_id = new_user.get('id')
                
                # Si des photos ont été téléchargées, les ajouter
                photo_files = request.files.getlist('photos')
                if photo_files and photo_files[0].filename:
                    for photo in photo_files:
                        upload_photo(user_id, photo)
                
                flash("Utilisateur créé avec succès!", "success")
                return redirect(url_for('view_user', user_id=user_id))
            else:
                flash(f"Erreur lors de la création de l'utilisateur: {response.status_code}", "error")
                return render_template('users/new.html', user=user_data)
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
            return render_template('users/new.html', user=user_data)
    
    return render_template('users/new.html', user={})

@app.route('/users/<user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    if request.method == 'POST':
        # Récupérer d'abord l'utilisateur existant pour préserver ses photos
        try:
            current_user_response = requests.get(f"{API_BASE_URL}/joueurs/{user_id}")
            if current_user_response.status_code != 200:
                flash(f"Erreur lors de la récupération de l'utilisateur: {current_user_response.status_code}", "error")
                return redirect(url_for('list_users'))
            
            current_user = current_user_response.json()
            
            # Déterminer quelles photos garder
            photos_to_keep = []
            if 'photos' in current_user and current_user['photos']:
                for i, photo in enumerate(current_user['photos']):
                    if photo and f'delete_photo_{i}' not in request.form:
                        photos_to_keep.append(photo)
            
            # Construire les données utilisateur avec les photos préservées
            user_data = {
                "username": request.form.get('username'),
                "prenom": request.form.get('prenom') or None,
                "nom": request.form.get('nom') or None,
                "email": request.form.get('email') or None,
                "telephone": request.form.get('telephone') or None,
                "nation": request.form.get('nation') or None,
                "club": request.form.get('club') or None,
                "photos": photos_to_keep
            }
            
            response = requests.put(f"{API_BASE_URL}/joueurs/{user_id}", json=user_data)
            if response.status_code == 200:
                # Si des photos ont été téléchargées, les ajouter
                photo_files = request.files.getlist('new_photos')
                if photo_files and photo_files[0].filename:
                    for photo in photo_files:
                        upload_photo(user_id, photo)
                
                flash("Utilisateur mis à jour avec succès!", "success")
                return redirect(url_for('view_user', user_id=user_id))
            else:
                flash(f"Erreur lors de la mise à jour de l'utilisateur: {response.status_code}", "error")
                return render_template('users/edit.html', user=user_data, user_id=user_id)
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
            return render_template('users/edit.html', user=request.form, user_id=user_id)
    
    try:
        response = requests.get(f"{API_BASE_URL}/joueurs/{user_id}")
        if response.status_code == 200:
            user = response.json()
            return render_template('users/edit.html', user=user, user_id=user_id)
        else:
            flash(f"Utilisateur non trouvé: {response.status_code}", "error")
            return redirect(url_for('list_users'))
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('list_users'))

def upload_photo(user_id, photo_file):
    """Télécharger une photo pour un utilisateur selon le format attendu par l'API."""
    try:
        # D'après la commande curl qui fonctionne, le paramètre attendu est "files" et non "file"
        files = {'files': (photo_file.filename, photo_file, photo_file.content_type)}
        
        # Ajouter les en-têtes appropriés pour s'assurer que le serveur comprend la requête
        headers = {
            'accept': 'application/json',
            'Content-Type': 'multipart/form-data'
        }
        
        # Déboguer les informations de la requête
        print(f"Envoi de fichier '{photo_file.filename}' à l'utilisateur ID: {user_id}")
        
        # Effectuer la requête 
        response = requests.post(
            f"{API_BASE_URL}/joueurs/{user_id}/photos", 
            files=files
            # Ne pas inclure les headers car requests gère automatiquement les headers pour les requêtes multipart/form-data
        )
        
        # Débogage de la réponse
        print(f"Code de réponse: {response.status_code}")
        if response.text:
            print(f"Contenu de la réponse: {response.text[:200]}...")
        
        if response.status_code not in (200, 201, 202):
            flash(f"Erreur lors du téléchargement de la photo: {response.status_code}", "error")
            return False
        
        flash("Photo téléchargée avec succès!", "success")
        return True
    except Exception as e:
        flash(f"Erreur lors du téléchargement de la photo: {str(e)}", "error")
        print(f"Exception complète: {str(e)}")
        return False

@app.route('/users/<user_id>/delete', methods=['POST'])
def delete_user(user_id):
    try:
        response = requests.delete(f"{API_BASE_URL}/joueurs/{user_id}")
        if response.status_code in (200, 204):
            flash("Utilisateur supprimé avec succès!", "success")
        else:
            flash(f"Erreur lors de la suppression de l'utilisateur: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('list_users'))

@app.route('/users/<user_id>/delete_photo/<int:photo_index>', methods=['POST'])
def delete_user_photo(user_id, photo_index):
    """Supprimer une photo spécifique d'un utilisateur."""
    try:
        # Appeler l'API pour supprimer la photo
        response = requests.delete(f"{API_BASE_URL}/joueurs/{user_id}/photos/{photo_index}")
        
        # Débogage
        print(f"Suppression de la photo {photo_index} pour l'utilisateur {user_id}")
        print(f"Code de réponse: {response.status_code}")
        
        if response.status_code in (200, 202, 204):
            flash("Photo supprimée avec succès!", "success")
        else:
            flash(f"Erreur lors de la suppression de la photo: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur lors de la suppression de la photo: {str(e)}", "error")
        print(f"Exception: {str(e)}")
    
    # Rediriger vers la page de l'utilisateur
    return redirect(url_for('view_user', user_id=user_id))

# Gestion des plugins
@app.route('/plugins')
def list_plugins():
    plugins = load_plugins()
    return render_template('plugins/list.html', plugins=plugins)

@app.route('/plugins/<plugin_name>/activate', methods=['POST'])
def activate_plugin(plugin_name):
    if plugin_name not in active_plugins:
        active_plugins.append(plugin_name)
        save_plugins_state()  # Sauvegarder l'état
        
        # Initialiser le plugin si nécessaire
        plugins = load_plugins()
        for plugin in plugins:
            if plugin['name'] == plugin_name:
                plugin_dir = Path(plugin['path'])
                plugin_file = plugin_dir / "plugin.py"
                
                if plugin_file.exists():
                    plugin_module_path = f"{PLUGINS_DIR}.{plugin_dir.name}.plugin"
                    try:
                        plugin_module = __import__(plugin_module_path, fromlist=['initialize'])
                        if hasattr(plugin_module, 'initialize'):
                            plugin_module.initialize()
                            print(f"Plugin {plugin_name} initialisé avec succès!")
                    except Exception as e:
                        print(f"Erreur lors de l'initialisation du plugin {plugin_name}: {e}")
        
        flash(f"Plugin {plugin_name} activé!", "success")
    return redirect(url_for('list_plugins'))

@app.route('/plugins/<plugin_name>/deactivate', methods=['POST'])
def deactivate_plugin(plugin_name):
    if plugin_name in active_plugins:
        active_plugins.remove(plugin_name)
        save_plugins_state()  # Sauvegarder l'état
        flash(f"Plugin {plugin_name} désactivé!", "success")
    return redirect(url_for('list_plugins'))

# Routes pour les plugins
@app.route('/evenements')
def list_evenements():
    # Vérifier si le plugin evenement est actif
    if 'evenement' not in active_plugins:
        flash("Le plugin Événement n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    # Récupérer les événements depuis l'API réelle
    try:
        response = requests.get(f"{API_BASE_URL}/evenements/", params={"skip": 0, "limit": 100})
        if response.status_code == 200:
            evenements = response.json()
            return render_template('plugins/evenement/list.html', evenements=evenements)
        else:
            flash(f"Erreur lors de la récupération des événements: {response.status_code}", "error")
            return render_template('plugins/evenement/list.html', evenements=[])
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return render_template('plugins/evenement/list.html', evenements=[])

@app.route('/evenements/nouveau', methods=['GET', 'POST'])
def add_evenement():
    # Vérifier si le plugin evenement est actif
    if 'evenement' not in active_plugins:
        flash("Le plugin Événement n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Récupérer les données du formulaire
        evenement_data = {
            "nom": request.form.get('nom'),
            "date_debut": request.form.get('date_debut'),
            "date_fin": request.form.get('date_fin'),
            "description": request.form.get('description'),
        }
        
        # Envoyer les données à l'API
        try:
            response = requests.post(f"{API_BASE_URL}/evenements/", json=evenement_data)
            if response.status_code in (200, 201):
                flash("Événement créé avec succès!", "success")
                return redirect(url_for('list_evenements'))
            else:
                flash(f"Erreur lors de la création de l'événement: {response.status_code}", "error")
                return render_template('plugins/evenement/new.html', evenement=evenement_data)
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
            return render_template('plugins/evenement/new.html', evenement=evenement_data)
    
    return render_template('plugins/evenement/new.html', evenement={})

@app.route('/evenements/<evenement_id>')
def view_evenement(evenement_id):
    # Vérifier si le plugin evenement est actif
    if 'evenement' not in active_plugins:
        flash("Le plugin Événement n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    # Récupérer les détails de l'événement
    try:
        response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        if response.status_code == 200:
            evenement = response.json()
            return render_template('plugins/evenement/view.html', evenement=evenement)
        else:
            flash(f"Événement non trouvé: {response.status_code}", "error")
            return redirect(url_for('list_evenements'))
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('list_evenements'))

@app.route('/evenements/<evenement_id>/edit', methods=['GET', 'POST'])
def edit_evenement(evenement_id):
    # Vérifier si le plugin evenement est actif
    if 'evenement' not in active_plugins:
        flash("Le plugin Événement n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Récupérer les données du formulaire
        evenement_data = {
            "nom": request.form.get('nom'),
            "date_debut": request.form.get('date_debut'),
            "date_fin": request.form.get('date_fin'),
            "description": request.form.get('description'),
        }
        
        # Envoyer les données à l'API
        try:
            response = requests.put(f"{API_BASE_URL}/evenements/{evenement_id}", json=evenement_data)
            if response.status_code == 200:
                flash("Événement mis à jour avec succès!", "success")
                return redirect(url_for('view_evenement', evenement_id=evenement_id))
            else:
                flash(f"Erreur lors de la mise à jour de l'événement: {response.status_code}", "error")
                return render_template('plugins/evenement/edit.html', evenement=evenement_data, evenement_id=evenement_id)
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
            return render_template('plugins/evenement/edit.html', evenement=evenement_data, evenement_id=evenement_id)
    
    # Récupérer les détails actuels de l'événement
    try:
        response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        if response.status_code == 200:
            evenement = response.json()
            return render_template('plugins/evenement/edit.html', evenement=evenement, evenement_id=evenement_id)
        else:
            flash(f"Événement non trouvé: {response.status_code}", "error")
            return redirect(url_for('list_evenements'))
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('list_evenements'))

@app.route('/evenements/<evenement_id>/delete', methods=['POST'])
def delete_evenement(evenement_id):
    # Vérifier si le plugin evenement est actif
    if 'evenement' not in active_plugins:
        flash("Le plugin Événement n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    # Supprimer l'événement via l'API
    try:
        response = requests.delete(f"{API_BASE_URL}/evenements/{evenement_id}")
        if response.status_code in (200, 204):
            flash("Événement supprimé avec succès!", "success")
        else:
            flash(f"Erreur lors de la suppression de l'événement: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('list_evenements'))

# Routes pour le plugin de phases
@app.route('/phases')
def list_phases():
    # Vérifier si le plugin phase est actif
    if 'phase' not in active_plugins:
        flash("Le plugin Phase n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    # Récupérer les templates de phases depuis l'API
    try:
        response = requests.get(f"{API_BASE_URL}/phases/")
        if response.status_code == 200:
            phases = response.json()
            return render_template('plugins/phase/list.html', phases=phases)
        else:
            flash(f"Erreur lors de la récupération des templates de phases: {response.status_code}", "error")
            return render_template('plugins/phase/list.html', phases=[])
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return render_template('plugins/phase/list.html', phases=[])

@app.route('/phases/nouveau', methods=['GET', 'POST'])
def add_phase():
    # Vérifier si le plugin phase est actif
    if 'phase' not in active_plugins:
        flash("Le plugin Phase n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Récupérer les données de base
        phase_data = {
            "nom": request.form.get('nom'),
            "description": request.form.get('description'),
            "type": request.form.get('type'),
            "type_id": request.form.get('type_id'),
            "format_id": request.form.get('format_id'),
            "ordre": int(request.form.get('ordre') or 1)
        }
        
        # Construire l'objet de configuration
        configuration = {
            "points_max": int(request.form.get('points_max') or 5),
            "format_type": request.form.get('format_type', 'poule'),
            "limite_temps": 'limite_temps' in request.form,
            "limite_points": 'limite_points' in request.form,
            "nombre_manches": int(request.form.get('nombre_manches') or 1),
            "temps_par_manche": int(request.form.get('temps_par_manche') or 3),
            "max_joueurs_poule": int(request.form.get('max_joueurs_poule') or 6),
            "min_joueurs_poule": int(request.form.get('min_joueurs_poule') or 3),
            "ideal_joueurs_poule": int(request.form.get('ideal_joueurs_poule') or 5)
        }
        phase_data["configuration"] = configuration
        
        # Construire l'objet de scoring
        place_points = {
            "1": int(request.form.get('place_1') or 10),
            "2": int(request.form.get('place_2') or 5),
            "3": int(request.form.get('place_3') or 0)
        }
        
        ordre_priorite = [
            request.form.get('priorite_1', 'Points de Victoire'),
            request.form.get('priorite_2', 'Indice (GoalAverage)'),
            request.form.get('priorite_3', 'Points mis'),
            request.form.get('priorite_4', 'Points Pris')
        ]
        
        # Traiter les points bonus (qui peuvent être multiples)
        bonus_points = []
        if 'bonus_condition[]' in request.form:
            bonus_conditions = request.form.getlist('bonus_condition[]')
            bonus_points_values = request.form.getlist('bonus_points[]')
            
            for i in range(len(bonus_conditions)):
                if bonus_conditions[i] and bonus_points_values[i]:
                    bonus_points.append({
                        "condition": bonus_conditions[i],
                        "points": int(bonus_points_values[i])
                    })
        
        scoring = {
            "placePoints": place_points,
            "pointsVictoire": int(request.form.get('points_victoire') or 3),
            "ordrePriorite": ordre_priorite,
            "bonusPoints": bonus_points
        }
        phase_data["scoring"] = scoring
        
        # Envoyer les données à l'API
        try:
            response = requests.post(f"{API_BASE_URL}/phases/", json=phase_data)
            if response.status_code in (200, 201):
                flash("Template de phase créé avec succès!", "success")
                return redirect(url_for('list_phases'))
            else:
                flash(f"Erreur lors de la création du template: {response.status_code}", "error")
                return render_template('plugins/phase/new.html', phase=phase_data)
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
            return render_template('plugins/phase/new.html', phase=phase_data)
    
    # Récupérer la liste des types et formats
    types = []
    formats = []
    try:
        types_response = requests.get(f"{API_BASE_URL}/types/")
        if types_response.status_code == 200:
            types = types_response.json()
        
        formats_response = requests.get(f"{API_BASE_URL}/formats/")
        if formats_response.status_code == 200:
            formats = formats_response.json()
    except Exception as e:
        flash(f"Erreur lors de la récupération des types et formats: {str(e)}", "warning")
    
    return render_template('plugins/phase/new.html', phase={}, types=types, formats=formats)

@app.route('/phases/<phase_id>')
def view_phase(phase_id):
    # Vérifier si le plugin phase est actif
    if 'phase' not in active_plugins:
        flash("Le plugin Phase n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    # Récupérer les détails du template
    try:
        # Récupérer le template de phase
        response = requests.get(f"{API_BASE_URL}/phases/{phase_id}")
        if response.status_code != 200:
            flash(f"Template non trouvé: {response.status_code}", "error")
            return redirect(url_for('list_phases'))
        
        phase = response.json()
        
        # Récupérer les informations du type et du format si présents
        type_info = None
        format_info = None
        
        if 'type_id' in phase and phase['type_id']:
            type_response = requests.get(f"{API_BASE_URL}/types/{phase['type_id']}")
            if type_response.status_code == 200:
                type_info = type_response.json()
        
        if 'format_id' in phase and phase['format_id']:
            format_response = requests.get(f"{API_BASE_URL}/formats/{phase['format_id']}")
            if format_response.status_code == 200:
                format_info = format_response.json()
        
        return render_template('plugins/phase/view.html', phase=phase, type_info=type_info, format_info=format_info)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('list_phases'))

@app.route('/phases/<phase_id>/edit', methods=['GET', 'POST'])
def edit_phase(phase_id):
    # Vérifier si le plugin phase est actif
    if 'phase' not in active_plugins:
        flash("Le plugin Phase n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Récupérer les données de base
        phase_data = {
            "nom": request.form.get('nom'),
            "description": request.form.get('description'),
            "type": request.form.get('type'),
            "type_id": request.form.get('type_id'),
            "format_id": request.form.get('format_id'),
            "ordre": int(request.form.get('ordre') or 1)
        }
        
        # Construire l'objet de configuration
        configuration = {
            "points_max": int(request.form.get('points_max') or 5),
            "format_type": request.form.get('format_type', 'poule'),
            "limite_temps": 'limite_temps' in request.form,
            "limite_points": 'limite_points' in request.form,
            "nombre_manches": int(request.form.get('nombre_manches') or 1),
            "temps_par_manche": int(request.form.get('temps_par_manche') or 3),
            "max_joueurs_poule": int(request.form.get('max_joueurs_poule') or 6),
            "min_joueurs_poule": int(request.form.get('min_joueurs_poule') or 3),
            "ideal_joueurs_poule": int(request.form.get('ideal_joueurs_poule') or 5)
        }
        phase_data["configuration"] = configuration
        
        # Construire l'objet de scoring
        place_points = {
            "1": int(request.form.get('place_1') or 10),
            "2": int(request.form.get('place_2') or 5),
            "3": int(request.form.get('place_3') or 0)
        }
        
        ordre_priorite = [
            request.form.get('priorite_1', 'Points de Victoire'),
            request.form.get('priorite_2', 'Indice (GoalAverage)'),
            request.form.get('priorite_3', 'Points mis'),
            request.form.get('priorite_4', 'Points Pris')
        ]
        
        # Traiter les points bonus (qui peuvent être multiples)
        bonus_points = []
        if 'bonus_condition[]' in request.form:
            bonus_conditions = request.form.getlist('bonus_condition[]')
            bonus_points_values = request.form.getlist('bonus_points[]')
            
            for i in range(len(bonus_conditions)):
                if bonus_conditions[i] and bonus_points_values[i]:
                    bonus_points.append({
                        "condition": bonus_conditions[i],
                        "points": int(bonus_points_values[i])
                    })
        
        scoring = {
            "placePoints": place_points,
            "pointsVictoire": int(request.form.get('points_victoire') or 3),
            "ordrePriorite": ordre_priorite,
            "bonusPoints": bonus_points
        }
        phase_data["scoring"] = scoring
        
        # Envoyer les données à l'API
        try:
            response = requests.put(f"{API_BASE_URL}/phases/{phase_id}", json=phase_data)
            if response.status_code == 200:
                flash("Template de phase mis à jour avec succès!", "success")
                return redirect(url_for('view_phase', phase_id=phase_id))
            else:
                flash(f"Erreur lors de la mise à jour du template: {response.status_code}", "error")
                return render_template('plugins/phase/edit.html', phase=phase_data, phase_id=phase_id)
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
            return render_template('plugins/phase/edit.html', phase=phase_data, phase_id=phase_id)
    
    # Récupérer les détails actuels du template et les listes de types et formats
    try:
        response = requests.get(f"{API_BASE_URL}/phases/{phase_id}")
        types_response = requests.get(f"{API_BASE_URL}/types/")
        formats_response = requests.get(f"{API_BASE_URL}/formats/")
        
        types = []
        formats = []
        
        if types_response.status_code == 200:
            types = types_response.json()
        
        if formats_response.status_code == 200:
            formats = formats_response.json()
            
        if response.status_code == 200:
            phase = response.json()
            return render_template('plugins/phase/edit.html', phase=phase, phase_id=phase_id, types=types, formats=formats)
        else:
            flash(f"Template non trouvé: {response.status_code}", "error")
            return redirect(url_for('list_phases'))
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('list_phases'))

@app.route('/phases/<phase_id>/delete', methods=['POST'])
def delete_phase(phase_id):
    # Vérifier si le plugin phase est actif
    if 'phase' not in active_plugins:
        flash("Le plugin Phase n'est pas activé!", "error")
        return redirect(url_for('index'))
    
    # Supprimer le template via l'API
    try:
        response = requests.delete(f"{API_BASE_URL}/phases/{phase_id}")
        if response.status_code in (200, 204):
            flash("Template de phase supprimé avec succès!", "success")
        else:
            flash(f"Erreur lors de la suppression du template: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('list_phases'))

@app.route('/evenements/phases')
def list_event_phases():
    # Vérifier si les plugins phase et evenement sont actifs
    if 'phase' not in active_plugins or 'evenement' not in active_plugins:
        flash("Les plugins Phase et Événement doivent être activés!", "error")
        return redirect(url_for('index'))
    
    # Récupérer la liste des événements
    try:
        response = requests.get(f"{API_BASE_URL}/evenements/")
        if response.status_code == 200:
            evenements = response.json()
            return render_template('plugins/phase/events.html', evenements=evenements)
        else:
            flash(f"Erreur lors de la récupération des événements: {response.status_code}", "error")
            return render_template('plugins/phase/events.html', evenements=[])
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return render_template('plugins/phase/events.html', evenements=[])

@app.route('/evenements/<evenement_id>/phases')
def view_event_phases(evenement_id):
    # Vérifier si les plugins phase et evenement sont actifs
    if 'phase' not in active_plugins or 'evenement' not in active_plugins:
        flash("Les plugins Phase et Événement doivent être activés!", "error")
        return redirect(url_for('index'))
    
    # Récupérer les détails de l'événement
    try:
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        if event_response.status_code != 200:
            flash(f"Événement non trouvé: {event_response.status_code}", "error")
            return redirect(url_for('list_event_phases'))
        
        evenement = event_response.json()
        
        # Récupérer les phases de l'événement
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        if phases_response.status_code == 200:
            phases = phases_response.json()
        else:
            phases = []
            if phases_response.status_code != 404:  # 404 est normal si aucune phase n'existe encore
                flash(f"Erreur lors de la récupération des phases: {phases_response.status_code}", "error")
        
        # Récupérer les templates de phases disponibles
        templates_response = requests.get(f"{API_BASE_URL}/phases/")
        if templates_response.status_code == 200:
            templates = templates_response.json()
        else:
            templates = []
            flash(f"Erreur lors de la récupération des templates: {templates_response.status_code}", "error")
        
        return render_template('plugins/phase/event_phases.html', 
                              evenement=evenement, 
                              phases=phases, 
                              templates=templates)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('list_event_phases'))

@app.route('/evenements/<evenement_id>/phases/add', methods=['POST'])
def add_event_phase(evenement_id):
    # Vérifier si les plugins phase et evenement sont actifs
    if 'phase' not in active_plugins or 'evenement' not in active_plugins:
        flash("Les plugins Phase et Événement doivent être activés!", "error")
        return redirect(url_for('index'))
    
    # Récupérer l'ID du template de phase
    phase_id = request.form.get('phase_id')
    if not phase_id:
        flash("Aucun template de phase sélectionné", "error")
        return redirect(url_for('view_event_phases', evenement_id=evenement_id))
    
    # Ajouter la phase à l'événement
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/phases", 
                               json={
                                   "phase_id": phase_id,
                                   "evenement_id": evenement_id
                               })
        
        if response.status_code in (200, 201):
            flash("Phase ajoutée à l'événement avec succès!", "success")
        else:
            error_detail = response.text
            flash(f"Erreur lors de l'ajout de la phase: {response.status_code} - {error_detail}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('view_event_phases', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/delete', methods=['POST'])
def delete_event_phase(evenement_id, phase_id):
    # Vérifier si les plugins phase et evenement sont actifs
    if 'phase' not in active_plugins or 'evenement' not in active_plugins:
        flash("Les plugins Phase et Événement doivent être activés!", "error")
        return redirect(url_for('index'))
    
    # Supprimer la phase de l'événement
    try:
        response = requests.delete(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}")
        if response.status_code in (200, 204):
            flash("Phase supprimée de l'événement avec succès!", "success")
        else:
            flash(f"Erreur lors de la suppression de la phase: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('view_event_phases', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/joueurs')
def view_phase_players(evenement_id, phase_id):
    # Vérifier si les plugins phase et evenement sont actifs
    if 'phase' not in active_plugins or 'evenement' not in active_plugins:
        flash("Les plugins Phase et Événement doivent être activés!", "error")
        return redirect(url_for('index'))
    
    try:
        # Récupérer les détails de l'événement et de la phase
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        phase_template_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}")
        
        if event_response.status_code != 200 or phase_template_response.status_code != 200:
            flash("Événement ou phase non trouvé", "error")
            return redirect(url_for('list_event_phases'))
        
        evenement = event_response.json()
        phase_template = phase_template_response.json()
        
        # Récupérer les joueurs de la phase
        players_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs")
        if players_response.status_code == 200:
            players = players_response.json()
        else:
            players = []
            if players_response.status_code != 404:  # 404 est normal si aucun joueur n'est inscrit
                flash(f"Erreur lors de la récupération des joueurs: {players_response.status_code}", "error")
        
        # Récupérer tous les joueurs disponibles
        all_players_response = requests.get(f"{API_BASE_URL}/joueurs")
        if all_players_response.status_code == 200:
            all_players = all_players_response.json()
            # Filtrer les joueurs qui ne sont pas déjà inscrits à cette phase
            player_ids = [p['joueur_id'] for p in players]
            available_players = [p for p in all_players if p['id'] not in player_ids]
        else:
            available_players = []
            flash(f"Erreur lors de la récupération de la liste des joueurs: {all_players_response.status_code}", "error")
        
        return render_template('plugins/phase/phase_players.html',
                              evenement=evenement,
                              phase=phase_template,
                              players=players,
                              available_players=available_players)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_event_phases', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/joueurs/add', methods=['POST'])
def add_phase_player(evenement_id, phase_id):
    # Vérifier si les plugins phase et evenement sont actifs
    if 'phase' not in active_plugins or 'evenement' not in active_plugins:
        flash("Les plugins Phase et Événement doivent être activés!", "error")
        return redirect(url_for('index'))
    
    # Récupérer l'ID du joueur
    joueur_id = request.form.get('joueur_id')
    if not joueur_id:
        flash("Aucun joueur sélectionné", "error")
        return redirect(url_for('view_phase_players', evenement_id=evenement_id, phase_id=phase_id))
    
    # Ajouter le joueur à la phase
    try:
        # L'API attend une liste de joueurs avec ordre_inscription
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs", 
                               json=[{
                                   "joueur_id": joueur_id,
                                   "ordre_inscription": 0  # Sera calculé automatiquement par l'API
                               }])
        
        if response.status_code in (200, 201):
            flash("Joueur ajouté à la phase avec succès!", "success")
        else:
            error_detail = response.text
            flash(f"Erreur lors de l'ajout du joueur: {response.status_code} - {error_detail}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('view_phase_players', evenement_id=evenement_id, phase_id=phase_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/joueurs/<joueur_id>/delete', methods=['POST'])
def delete_phase_player(evenement_id, phase_id, joueur_id):
    # Vérifier si les plugins phase et evenement sont actifs
    if 'phase' not in active_plugins or 'evenement' not in active_plugins:
        flash("Les plugins Phase et Événement doivent être activés!", "error")
        return redirect(url_for('index'))
    
    # Supprimer le joueur de la phase
    try:
        response = requests.delete(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs/{joueur_id}")
        if response.status_code in (200, 204):
            flash("Joueur retiré de la phase avec succès!", "success")
        else:
            flash(f"Erreur lors du retrait du joueur: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('view_phase_players', evenement_id=evenement_id, phase_id=phase_id))

# Routes pour les Types
@app.route('/types')
def list_types():
    """Liste tous les types de phases"""
    try:
        response = requests.get(f"{API_BASE_URL}/types/")
        types = response.json() if response.status_code == 200 else []
        return render_template('types/list.html', types=types)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/types/nouveau', methods=['GET', 'POST'])
def create_type():
    """Créer un nouveau type"""
    if request.method == 'POST':
        try:
            # Construire la config des résultats
            resultats_config = {
                "classement": request.form.get('resultats_classement') == 'on',
                "points": request.form.get('resultats_points') == 'on',
                "actions": request.form.get('resultats_actions') == 'on'
            }
            
            type_data = {
                "nom": request.form.get('nom'),
                "proprietes": {},
                "resultats_config": resultats_config
            }
            
            response = requests.post(f"{API_BASE_URL}/types/", json=type_data)
            if response.status_code in (200, 201):
                flash("Type créé avec succès!", "success")
                return redirect(url_for('list_types'))
            else:
                flash(f"Erreur lors de la création: {response.status_code} - {response.text}", "error")
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
    
    return render_template('types/form.html', type={})

@app.route('/types/<type_id>/edit', methods=['GET', 'POST'])
def edit_type(type_id):
    """Modifier un type existant"""
    if request.method == 'POST':
        try:
            # Construire la config des résultats
            resultats_config = {
                "classement": request.form.get('resultats_classement') == 'on',
                "points": request.form.get('resultats_points') == 'on',
                "actions": request.form.get('resultats_actions') == 'on'
            }
            
            type_data = {
                "nom": request.form.get('nom'),
                "proprietes": {},
                "resultats_config": resultats_config
            }
            
            response = requests.put(f"{API_BASE_URL}/types/{type_id}", json=type_data)
            if response.status_code == 200:
                flash("Type modifié avec succès!", "success")
                return redirect(url_for('list_types'))
            else:
                flash(f"Erreur lors de la modification: {response.status_code} - {response.text}", "error")
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
    
    # GET - Récupérer le type existant
    try:
        response = requests.get(f"{API_BASE_URL}/types/{type_id}")
        if response.status_code == 200:
            type_data = response.json()
            return render_template('types/form.html', type=type_data)
        else:
            flash(f"Type non trouvé: {response.status_code}", "error")
            return redirect(url_for('list_types'))
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('list_types'))

@app.route('/types/<type_id>/delete', methods=['POST'])
def delete_type(type_id):
    """Supprimer un type"""
    try:
        response = requests.delete(f"{API_BASE_URL}/types/{type_id}")
        if response.status_code in (200, 204):
            flash("Type supprimé avec succès!", "success")
        else:
            flash(f"Erreur lors de la suppression: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('list_types'))

if __name__ == '__main__':
    load_plugins_state()  # Charger l'état des plugins au démarrage
    initialize_active_plugins()
    app.run(debug=True, port=5000) 
