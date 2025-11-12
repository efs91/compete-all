from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import requests
import os
import json
from datetime import datetime
from dateutil import parser as date_parser

app = Flask(__name__)
app.secret_key = "compete-all-orga-secret-key"

# Configuration de l'API
API_BASE_URL = "https://benribs.fr/compete-all"

# ============================================
# ROUTES PRINCIPALES
# ============================================

@app.route('/')
def index():
    """Page d'accueil avec liste des événements"""
    try:
        response = requests.get(f"{API_BASE_URL}/evenements")
        if response.status_code == 200:
            evenements = response.json()
            return render_template('index.html', evenements=evenements)
        else:
            flash(f"Erreur lors de la récupération des événements: {response.status_code}", "error")
            return render_template('index.html', evenements=[])
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return render_template('index.html', evenements=[])

# ============================================
# GESTION DES ÉVÉNEMENTS
# ============================================

@app.route('/evenements/nouveau', methods=['GET', 'POST'])
def create_evenement():
    """Créer un nouvel événement"""
    if request.method == 'POST':
        evenement_data = {
            "nom": request.form.get('nom'),
            "date_debut": request.form.get('date_debut'),
            "date_fin": request.form.get('date_fin'),
            "description": request.form.get('description') or None
        }
        
        try:
            response = requests.post(f"{API_BASE_URL}/evenements", json=evenement_data)
            if response.status_code in (200, 201):
                new_event = response.json()
                flash("Événement créé avec succès!", "success")
                return redirect(url_for('view_evenement', evenement_id=new_event['id']))
            else:
                flash(f"Erreur lors de la création: {response.status_code}", "error")
                return render_template('evenements/form.html', evenement=evenement_data, mode='create')
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
            return render_template('evenements/form.html', evenement=evenement_data, mode='create')
    
    return render_template('evenements/form.html', evenement={}, mode='create')

@app.route('/evenements/<evenement_id>')
def view_evenement(evenement_id):
    """Voir les détails d'un événement"""
    try:
        # Récupérer l'événement
        response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        if response.status_code != 200:
            flash("Événement non trouvé", "error")
            return redirect(url_for('index'))
        
        evenement = response.json()
        
        # Récupérer les phases de l'événement
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        phases = phases_response.json() if phases_response.status_code == 200 else []
        
        # Récupérer les statistiques
        stats = get_event_stats(evenement_id)
        
        return render_template('evenements/view.html', 
                             evenement=evenement, 
                             phases=phases,
                             stats=stats)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/evenements/<evenement_id>/edit', methods=['GET', 'POST'])
def edit_evenement(evenement_id):
    """Modifier un événement"""
    if request.method == 'POST':
        evenement_data = {
            "nom": request.form.get('nom'),
            "date_debut": request.form.get('date_debut'),
            "date_fin": request.form.get('date_fin'),
            "description": request.form.get('description') or None
        }
        
        try:
            response = requests.put(f"{API_BASE_URL}/evenements/{evenement_id}", json=evenement_data)
            if response.status_code == 200:
                flash("Événement modifié avec succès!", "success")
                return redirect(url_for('view_evenement', evenement_id=evenement_id))
            else:
                flash(f"Erreur lors de la modification: {response.status_code}", "error")
                return render_template('evenements/form.html', evenement=evenement_data, mode='edit', evenement_id=evenement_id)
        except Exception as e:
            flash(f"Erreur: {str(e)}", "error")
            return render_template('evenements/form.html', evenement=evenement_data, mode='edit', evenement_id=evenement_id)
    
    # GET
    try:
        response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        if response.status_code == 200:
            evenement = response.json()
            return render_template('evenements/form.html', evenement=evenement, mode='edit', evenement_id=evenement_id)
        else:
            flash("Événement non trouvé", "error")
            return redirect(url_for('index'))
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/evenements/<evenement_id>/delete', methods=['POST'])
def delete_evenement(evenement_id):
    """Supprimer un événement"""
    try:
        response = requests.delete(f"{API_BASE_URL}/evenements/{evenement_id}")
        if response.status_code in (200, 204):
            flash("Événement supprimé avec succès!", "success")
        else:
            flash(f"Erreur lors de la suppression: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('index'))

# ============================================
# GESTION DES PHASES
# ============================================

@app.route('/evenements/<evenement_id>/phases')
def manage_phases(evenement_id):
    """Gérer les phases d'un événement"""
    try:
        # Récupérer l'événement
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        if event_response.status_code != 200:
            flash("Événement non trouvé", "error")
            return redirect(url_for('index'))
        
        evenement = event_response.json()
        
        # Récupérer les phases de l'événement
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        phases = phases_response.json() if phases_response.status_code == 200 else []
        
        # Récupérer tous les templates de phases disponibles
        templates_response = requests.get(f"{API_BASE_URL}/phases")
        templates = templates_response.json() if templates_response.status_code == 200 else []
        
        return render_template('phases/manage.html', 
                             evenement=evenement, 
                             phases=phases, 
                             templates=templates)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_evenement', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/add', methods=['POST'])
def add_phase(evenement_id):
    """Ajouter une phase à l'événement"""
    phase_id = request.form.get('phase_id')
    if not phase_id:
        flash("Aucune phase sélectionnée", "error")
        return redirect(url_for('manage_phases', evenement_id=evenement_id))
    
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/phases",
                               json={
                                   "phase_id": phase_id,
                                   "evenement_id": evenement_id
                               })
        if response.status_code in (200, 201):
            flash("Phase ajoutée avec succès!", "success")
        else:
            flash(f"Erreur lors de l'ajout: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('manage_phases', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/delete', methods=['POST'])
def remove_phase(evenement_id, phase_id):
    """Retirer une phase de l'événement"""
    try:
        response = requests.delete(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}")
        if response.status_code in (200, 204):
            flash("Phase retirée avec succès!", "success")
        else:
            flash(f"Erreur lors du retrait: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('manage_phases', evenement_id=evenement_id))

# ============================================
# GESTION DES INSCRIPTIONS
# ============================================

@app.route('/evenements/<evenement_id>/inscriptions')
def manage_inscriptions(evenement_id):
    """Gérer les inscriptions à un événement"""
    try:
        # Récupérer l'événement
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        if event_response.status_code != 200:
            flash("Événement non trouvé", "error")
            return redirect(url_for('index'))
        
        evenement = event_response.json()
        
        # Récupérer les phases de l'événement
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        phases = phases_response.json() if phases_response.status_code == 200 else []
        
        # Pour chaque phase, récupérer les joueurs inscrits
        for phase in phases:
            joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase['id']}/joueurs")
            phase['joueurs'] = joueurs_response.json() if joueurs_response.status_code == 200 else []
        
        # Récupérer tous les joueurs disponibles
        all_players_response = requests.get(f"{API_BASE_URL}/joueurs")
        all_players = all_players_response.json() if all_players_response.status_code == 200 else []
        
        return render_template('inscriptions/manage.html', 
                             evenement=evenement, 
                             phases=phases,
                             all_players=all_players)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_evenement', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/inscriptions/add', methods=['POST'])
def add_inscription(evenement_id, phase_id):
    """Ajouter un joueur à une phase"""
    joueur_id = request.form.get('joueur_id')
    if not joueur_id:
        flash("Aucun joueur sélectionné", "error")
        return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))
    
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs",
                               json=[{
                                   "joueur_id": joueur_id,
                                   "ordre_inscription": 0
                               }])
        if response.status_code in (200, 201):
            flash("Joueur inscrit avec succès!", "success")
        else:
            flash(f"Erreur lors de l'inscription: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/inscriptions/<joueur_id>/delete', methods=['POST'])
def remove_inscription(evenement_id, phase_id, joueur_id):
    """Retirer un joueur d'une phase"""
    try:
        response = requests.delete(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs/{joueur_id}")
        if response.status_code in (200, 204):
            flash("Joueur retiré avec succès!", "success")
        else:
            flash(f"Erreur lors du retrait: {response.status_code}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))

# ============================================
# GÉNÉRATION DES RENCONTRES
# ============================================

@app.route('/evenements/<evenement_id>/phases/<phase_id>/generate', methods=['GET', 'POST'])
def generate_rencontres(evenement_id, phase_id):
    """Générer les rencontres pour une phase"""
    if request.method == 'POST':
        try:
            # Récupérer les joueurs de la phase
            joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs")
            if joueurs_response.status_code != 200:
                flash("Impossible de récupérer les joueurs", "error")
                return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))
            
            joueurs = joueurs_response.json()
            
            # Récupérer la configuration de la phase
            phase_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}")
            if phase_response.status_code != 200:
                flash("Phase non trouvée", "error")
                return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))
            
            phase = phase_response.json()
            
            # Générer les rencontres selon le type de phase
            rencontres = generate_matches_algorithm(joueurs, phase)
            
            # Créer les rencontres via l'API
            created_count = 0
            for rencontre_data in rencontres:
                response = requests.post(f"{API_BASE_URL}/phases/{phase_id}/rencontres",
                            json={
                                "evenement_id": evenement_id,
                                **rencontre_data
                            })
                print(f"DEBUG - Création rencontre: status={response.status_code}, data={rencontre_data}")
                if response.status_code in (200, 201):
                    created_count += 1
                else:
                    print(f"DEBUG - Erreur: {response.text}")
            
            flash(f"{created_count}/{len(rencontres)} rencontres générées avec succès!", "success")
            return redirect(url_for('view_rencontres', evenement_id=evenement_id, phase_id=phase_id))
            
        except Exception as e:
            flash(f"Erreur lors de la génération: {str(e)}", "error")
            return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))
    
    # GET - Afficher la page de confirmation
    try:
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        phase_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}")
        joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs")
        
        evenement = event_response.json() if event_response.status_code == 200 else {}
        phase = phase_response.json() if phase_response.status_code == 200 else {}
        joueurs = joueurs_response.json() if joueurs_response.status_code == 200 else []
        
        return render_template('rencontres/generate.html',
                             evenement=evenement,
                             phase=phase,
                             joueurs=joueurs)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))

# ============================================
# GESTION DES RENCONTRES ET RÉSULTATS
# ============================================

@app.route('/evenements/<evenement_id>/phases/<phase_id>/rencontres')
def view_rencontres(evenement_id, phase_id):
    """Voir les rencontres d'une phase"""
    try:
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        phase_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}")
        rencontres_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}/rencontres")
        
        # Debug
        print(f"DEBUG - URL: {API_BASE_URL}/phases/{phase_id}/rencontres")
        print(f"DEBUG - Status: {rencontres_response.status_code}")
        print(f"DEBUG - Response: {rencontres_response.text[:500] if rencontres_response.text else 'Empty'}")
        
        evenement = event_response.json() if event_response.status_code == 200 else {}
        phase = phase_response.json() if phase_response.status_code == 200 else {}
        rencontres = rencontres_response.json() if rencontres_response.status_code == 200 else []
        
        print(f"DEBUG - Nombre de rencontres: {len(rencontres)}")
        
        # Pour chaque rencontre, récupérer les résultats et les infos des participants
        all_joueurs = {}  # Cache pour éviter de requêter plusieurs fois le même joueur
        for rencontre in rencontres:
            resultats_response = requests.get(f"{API_BASE_URL}/rencontres/{rencontre['id']}/resultats")
            rencontre['resultats'] = resultats_response.json() if resultats_response.status_code == 200 else []
            
            # Récupérer les infos des participants
            if rencontre.get('participants'):
                rencontre['participants_details'] = []
                for joueur_id in rencontre['participants']:
                    if joueur_id not in all_joueurs:
                        joueur_response = requests.get(f"{API_BASE_URL}/joueurs/{joueur_id}")
                        if joueur_response.status_code == 200:
                            all_joueurs[joueur_id] = joueur_response.json()
                        else:
                            all_joueurs[joueur_id] = {'id': joueur_id, 'username': 'Inconnu', 'club': ''}
                    rencontre['participants_details'].append(all_joueurs[joueur_id])
        
        return render_template('rencontres/list.html',
                             evenement=evenement,
                             phase=phase,
                             rencontres=rencontres)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_evenement', evenement_id=evenement_id))

@app.route('/rencontres/<rencontre_id>/resultats', methods=['GET', 'POST'])
def edit_resultats(rencontre_id):
    """Saisir les résultats d'une rencontre"""
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            participants = request.form.getlist('participant_id')
            classements = request.form.getlist('classement')
            points = request.form.getlist('points')
            actions = request.form.getlist('actions')
            
            # Créer les résultats
            for i, participant_id in enumerate(participants):
                resultat_data = {"participant_id": participant_id}
                
                # Ajouter classement si présent
                if i < len(classements) and classements[i]:
                    resultat_data["classement"] = int(classements[i])
                
                # Ajouter points si présent
                if i < len(points) and points[i]:
                    resultat_data["points"] = int(points[i])
                
                # Parser les actions JSON si présentes
                if i < len(actions) and actions[i] and actions[i].strip():
                    try:
                        import json
                        resultat_data["actions"] = json.loads(actions[i])
                    except:
                        resultat_data["actions"] = {"note": actions[i]}
                
                requests.post(f"{API_BASE_URL}/rencontres/{rencontre_id}/resultats",
                            json=resultat_data)
            
            flash("Résultats enregistrés avec succès!", "success")
            return redirect(request.referrer or url_for('index'))
            
        except Exception as e:
            flash(f"Erreur lors de l'enregistrement: {str(e)}", "error")
            return redirect(request.referrer or url_for('index'))
    
    # GET
    try:
        rencontre_response = requests.get(f"{API_BASE_URL}/rencontres/{rencontre_id}")
        resultats_response = requests.get(f"{API_BASE_URL}/rencontres/{rencontre_id}/resultats")
        
        rencontre = rencontre_response.json() if rencontre_response.status_code == 200 else {}
        resultats = resultats_response.json() if resultats_response.status_code == 200 else []
        
        # Récupérer la phase et son type pour connaître la config des résultats
        resultats_config = {"classement": True, "points": True, "actions": False}  # Défaut
        if rencontre.get('phase_id'):
            phase_response = requests.get(f"{API_BASE_URL}/phases/{rencontre['phase_id']}")
            if phase_response.status_code == 200:
                phase = phase_response.json()
                if phase.get('type_id'):
                    type_response = requests.get(f"{API_BASE_URL}/types/{phase['type_id']}")
                    if type_response.status_code == 200:
                        type_data = type_response.json()
                        if type_data.get('resultats_config'):
                            resultats_config = type_data['resultats_config']
        
        # Récupérer les infos des participants
        participants_details = []
        if rencontre.get('participants'):
            for joueur_id in rencontre['participants']:
                joueur_response = requests.get(f"{API_BASE_URL}/joueurs/{joueur_id}")
                if joueur_response.status_code == 200:
                    participants_details.append(joueur_response.json())
                else:
                    participants_details.append({'id': joueur_id, 'username': 'Inconnu', 'club': ''})
        
        return render_template('rencontres/resultats.html',
                             rencontre=rencontre,
                             resultats=resultats,
                             participants_details=participants_details,
                             resultats_config=resultats_config)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('index'))

# ============================================
# CLASSEMENTS
# ============================================

@app.route('/evenements/<evenement_id>/classements')
def view_classements(evenement_id):
    """Voir les classements d'un événement"""
    try:
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        evenement = event_response.json() if event_response.status_code == 200 else {}
        
        # Récupérer les classements
        classements_response = requests.get(f"{API_BASE_URL}/classements/evenements/{evenement_id}/classements")
        classements = classements_response.json() if classements_response.status_code == 200 else []
        
        # Récupérer les phases
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        phases = phases_response.json() if phases_response.status_code == 200 else []
        
        # Pour chaque phase, récupérer son classement
        for phase in phases:
            phase_classement_response = requests.get(f"{API_BASE_URL}/classements/phases/{phase['id']}/classements")
            phase['classements'] = phase_classement_response.json() if phase_classement_response.status_code == 200 else []
        
        return render_template('classements/view.html',
                             evenement=evenement,
                             classements=classements,
                             phases=phases)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_evenement', evenement_id=evenement_id))

# ============================================
# UTILITAIRES
# ============================================

def get_event_stats(evenement_id):
    """Récupérer les statistiques d'un événement"""
    stats = {
        'total_joueurs': 0,
        'total_rencontres': 0,
        'rencontres_terminees': 0,
        'phases_count': 0
    }
    
    try:
        # Compter les phases
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        if phases_response.status_code == 200:
            phases = phases_response.json()
            stats['phases_count'] = len(phases)
            
            # Compter les joueurs uniques
            joueurs_ids = set()
            for phase in phases:
                joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase['id']}/joueurs")
                if joueurs_response.status_code == 200:
                    joueurs = joueurs_response.json()
                    for joueur in joueurs:
                        joueurs_ids.add(joueur['joueur_id'])
                
                # Compter les rencontres
                rencontres_response = requests.get(f"{API_BASE_URL}/phases/{phase['id']}/rencontres")
                if rencontres_response.status_code == 200:
                    rencontres = rencontres_response.json()
                    stats['total_rencontres'] += len(rencontres)
                    
                    # Compter les rencontres terminées (avec résultats)
                    for rencontre in rencontres:
                        resultats_response = requests.get(f"{API_BASE_URL}/rencontres/{rencontre['id']}/resultats")
                        if resultats_response.status_code == 200 and resultats_response.json():
                            stats['rencontres_terminees'] += 1
            
            stats['total_joueurs'] = len(joueurs_ids)
    except:
        pass
    
    return stats

def generate_matches_algorithm(joueurs, phase):
    """Algorithme de génération des rencontres selon le type de phase"""
    rencontres = []
    
    # TODO: Implémenter les algorithmes selon le type
    # - Poules: tous contre tous
    # - Élimination directe: bracket tournament
    # - Swiss system: etc.
    
    # Pour l'instant: tous contre tous simple (round-robin)
    joueurs_list = [j['joueur_id'] for j in joueurs]
    
    # Générer toutes les combinaisons possibles
    for i in range(len(joueurs_list)):
        for j in range(i + 1, len(joueurs_list)):
            rencontres.append({
                "participants": [joueurs_list[i], joueurs_list[j]]
            })
    
    print(f"DEBUG - Génération de {len(rencontres)} rencontres pour {len(joueurs_list)} joueurs")
    return rencontres

# ============================================
# LANCEMENT
# ============================================

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
