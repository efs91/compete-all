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
        
        # Calculer le classement provisoire pour chaque phase
        phases_classements = {}
        for phase in phases:
            joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase['id']}/joueurs")
            if joueurs_response.status_code == 200:
                joueurs = joueurs_response.json()
                classement = calculate_provisional_ranking(phase['id'], joueurs)
                phases_classements[phase['id']] = classement
        
        return render_template('evenements/view.html', 
                             evenement=evenement, 
                             phases=phases,
                             stats=stats,
                             phases_classements=phases_classements)
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
    """Ajouter une phase à l'événement avec configuration de qualification"""
    phase_id = request.form.get('phase_id')
    if not phase_id:
        flash("Aucune phase sélectionnée", "error")
        return redirect(url_for('manage_phases', evenement_id=evenement_id))
    
    # Construire la configuration de qualification
    config_qualification = None
    mode_qualification = request.form.get('mode_qualification')
    
    if mode_qualification and mode_qualification != '':
        # Construire les critères de tri
        criteres = []
        if request.form.get('critere_victoires'):
            criteres.append('victoires')
        if request.form.get('critere_vm'):
            criteres.append('vm')
        if request.form.get('critere_indice'):
            criteres.append('indice')
        if request.form.get('critere_td'):
            criteres.append('touches_donnees')
        
        config_qualification = {
            'mode': mode_qualification,
            'criteres_tri': criteres if criteres else ['victoires', 'vm', 'indice']
        }
        
        # Ajouter nb_qualifies ou pourcentage selon le type de sélection
        if mode_qualification != 'tous_qualifies':
            type_selection = request.form.get('type_selection', 'nombre')
            if type_selection == 'pourcentage':
                config_qualification['pourcentage_qualifies'] = int(request.form.get('pourcentage_qualifies', 50))
            else:
                config_qualification['nb_qualifies'] = int(request.form.get('nb_qualifies', 0))
    
    # Construire la configuration des décalages de poules
    config_decalages = {
        'decalage_club': bool(request.form.get('decalage_club')),
        'decalage_nation': bool(request.form.get('decalage_nation'))
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/phases",
                               json={
                                   "phase_id": phase_id,
                                   "evenement_id": evenement_id,
                                   "config_qualification": config_qualification,
                                   "config_decalages": config_decalages
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

@app.route('/evenements/<evenement_id>/phases/reorder', methods=['PUT'])
def reorder_phases(evenement_id):
    """Proxy pour réorganiser les phases via l'API FastAPI"""
    try:
        phase_orders = request.get_json()
        response = requests.put(
            f"{API_BASE_URL}/evenements/{evenement_id}/phases/reorder",
            json=phase_orders
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/evenements/<evenement_id>/lancer', methods=['POST'])
def lancer_competition(evenement_id):
    """Lance la compétition en inscrivant tous les joueurs à la première phase"""
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/lancer")
        
        if response.status_code in (200, 201):
            result = response.json()
            flash(f"🎯 Compétition lancée avec succès !", "success")
            flash(f"✅ {result['joueurs_inscrits']} joueurs inscrits à la première phase", "success")
            flash(f"📊 {result['nb_poules']} poules créées", "success")
            flash(f"⚔️ {result['rencontres_creees']} rencontres générées", "success")
        else:
            error_detail = response.json().get('detail', response.text)
            flash(f"Erreur lors du lancement: {error_detail}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('view_evenement', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/relancer', methods=['POST'])
def relancer_competition(evenement_id):
    """Relance la compétition : supprime toutes les données et remet à zéro"""
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/relancer")
        
        if response.status_code in (200, 201):
            flash(f"🔄 Compétition relancée : toutes les données ont été supprimées", "success")
        else:
            error_detail = response.json().get('detail', response.text)
            flash(f"Erreur lors du relancement: {error_detail}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('view_evenement', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/progresser', methods=['POST'])
def progresser_phase(evenement_id, phase_id):
    """Progresse vers la phase suivante : qualifie et lance la phase suivante"""
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/progresser")
        
        if response.status_code in (200, 201):
            result = response.json()
            flash(f"🎉 Progression réussie vers la phase suivante !", "success")
            flash(f"✅ {result['joueurs_qualifies']} joueurs qualifiés", "success")
            if result.get('nb_poules_creees', 0) > 0:
                flash(f"📊 {result['nb_poules_creees']} poules créées", "success")
            if result.get('rencontres_creees', 0) > 0:
                flash(f"⚔️ {result['rencontres_creees']} rencontres générées", "success")
            return redirect(url_for('manage_phases', evenement_id=evenement_id))
        else:
            error_detail = response.json().get('detail', response.text)
            flash(f"Erreur lors de la progression: {error_detail}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('view_evenement', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/qualifier', methods=['POST'])
def qualifier_phase(evenement_id, phase_id):
    """Qualifie automatiquement les joueurs pour la phase suivante"""
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/qualifier")
        
        if response.status_code in (200, 201):
            result = response.json()
            flash(f"✅ {result['joueurs_qualifies']} joueurs qualifiés pour la phase suivante (mode: {result['mode']})", "success")
        else:
            error_detail = response.json().get('detail', response.text)
            flash(f"Erreur lors de la qualification: {error_detail}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('view_rencontres', evenement_id=evenement_id, phase_id=phase_id))

# ============================================
# GESTION DES INSCRIPTIONS
# ============================================

@app.route('/evenements/<evenement_id>/inscriptions')
def manage_inscriptions(evenement_id):
    """Gérer les inscriptions globales à un événement"""
    try:
        # Récupérer l'événement
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        if event_response.status_code != 200:
            flash("Événement non trouvé", "error")
            return redirect(url_for('index'))
        
        evenement = event_response.json()
        
        # Récupérer les joueurs inscrits à l'événement
        inscriptions_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/inscriptions")
        joueurs_inscrits = inscriptions_response.json() if inscriptions_response.status_code == 200 else []
        
        # Récupérer tous les joueurs disponibles
        all_players_response = requests.get(f"{API_BASE_URL}/joueurs")
        all_players = all_players_response.json() if all_players_response.status_code == 200 else []
        
        # Filtrer les joueurs non inscrits
        joueurs_inscrits_ids = [j['id'] for j in joueurs_inscrits]
        joueurs_disponibles = [p for p in all_players if p['id'] not in joueurs_inscrits_ids]
        
        return render_template('inscriptions/manage.html', 
                             evenement=evenement, 
                             joueurs_inscrits=joueurs_inscrits,
                             joueurs_disponibles=joueurs_disponibles)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_evenement', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/inscriptions/add', methods=['POST'])
def add_event_inscription(evenement_id):
    """Ajouter un joueur à l'événement"""
    joueur_id = request.form.get('joueur_id')
    
    if not joueur_id:
        flash("Veuillez sélectionner un joueur", "error")
        return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))
    
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/inscriptions/{joueur_id}")
        
        if response.status_code in (200, 201):
            flash("Joueur inscrit avec succès", "success")
        else:
            flash(f"Erreur lors de l'inscription: {response.text}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/inscriptions/<joueur_id>/delete', methods=['POST'])
def remove_event_inscription(evenement_id, joueur_id):
    """Retirer un joueur de l'événement"""
    try:
        response = requests.delete(f"{API_BASE_URL}/evenements/{evenement_id}/inscriptions/{joueur_id}")
        
        if response.status_code in (200, 204):
            flash("Joueur retiré avec succès", "success")
        else:
            flash(f"Erreur lors du retrait: {response.text}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    return redirect(url_for('manage_inscriptions', evenement_id=evenement_id))

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

@app.route('/evenements/<evenement_id>/phases/<phase_id>/poules/generer', methods=['POST'])
def generer_poules(evenement_id, phase_id):
    """Générer automatiquement les poules pour une phase"""
    try:
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/poules/generer")
        
        if response.status_code in (200, 201):
            result = response.json()
            flash(f"✅ {result['nb_poules']} poules et {result.get('rencontres_creees', 0)} rencontres créées avec {result['nb_joueurs_total']} joueurs", "success")
            # Afficher les détails des poules
            for poule in result.get('poules', []):
                flash(f"   • {poule['nom']} : {len(poule['joueurs'])} joueurs", "info")
        else:
            error_detail = response.json().get('detail', response.text)
            flash(f"Erreur lors de la génération des poules: {error_detail}", "error")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    
    # Retourner sur la page rencontres pour voir les poules créées
    return redirect(url_for('view_rencontres', evenement_id=evenement_id, phase_id=phase_id))

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
                #print(f"DEBUG - Création rencontre: status={response.status_code}, data={rencontre_data}")
                if response.status_code in (200, 201):
                    created_count += 1
                else:
                    pass  # Erreur de création
                    #print(f"DEBUG - Erreur: {response.text}")
            
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
    """Voir les rencontres d'une phase - VERSION OPTIMISÉE"""
    try:
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        # Récupérer la phase avec sa relation dans l'événement (contient config_qualification)
        phase_in_event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        
        # Utiliser la nouvelle route optimisée qui retourne tout en une seule requête
        rencontres_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}/rencontres-complete")
        
        # Récupérer les poules de cette phase
        poules_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/poules")
        
        evenement = event_response.json() if event_response.status_code == 200 else {}
        phases_in_event = phase_in_event_response.json() if phase_in_event_response.status_code == 200 else []
        
        # Trouver la phase actuelle avec sa config_qualification
        phase = next((p for p in phases_in_event if p['id'] == phase_id), {})
        rencontres = rencontres_response.json() if rencontres_response.status_code == 200 else []
        poules = poules_response.json() if poules_response.status_code == 200 else []
        
        # Organiser les rencontres par poule et calculer la progression
        rencontres_by_poule = {}
        progression_poules = {}
        
        for rencontre in rencontres:
            poule_id = rencontre.get('poule_id', 'no_poule')
            if poule_id not in rencontres_by_poule:
                rencontres_by_poule[poule_id] = []
                progression_poules[poule_id] = {'total': 0, 'terminees': 0}
            
            rencontres_by_poule[poule_id].append(rencontre)
            progression_poules[poule_id]['total'] += 1
            
            # Compter si la rencontre a des résultats
            if rencontre.get('resultats') and len(rencontre['resultats']) > 0:
                progression_poules[poule_id]['terminees'] += 1
        
        # Récupérer les joueurs inscrits et calculer le classement provisoire
        joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs")
        joueurs = joueurs_response.json() if joueurs_response.status_code == 200 else []
        classement = calculate_provisional_ranking(phase_id, joueurs)
        
        # Détecter le type de phase pour afficher le bon mode
        type_general = phase.get('type_general', 'poule')
        
        return render_template('rencontres/list.html',
                             evenement=evenement,
                             phase=phase,
                             type_general=type_general,
                             rencontres=rencontres,
                             poules=poules,
                             rencontres_by_poule=rencontres_by_poule,
                             progression_poules=progression_poules,
                             classement=classement)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_evenement', evenement_id=evenement_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/tableau')
def view_tableau_bracket(evenement_id, phase_id):
    """Afficher le tableau d'élimination directe (bracket)"""
    import math
    
    try:
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        phase_in_event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        rencontres_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}/rencontres-complete")
        joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs")
        
        evenement = event_response.json() if event_response.status_code == 200 else {}
        phases_in_event = phase_in_event_response.json() if phase_in_event_response.status_code == 200 else []
        phase = next((p for p in phases_in_event if p['id'] == phase_id), {})
        rencontres = rencontres_response.json() if rencontres_response.status_code == 200 else []
        joueurs_data = joueurs_response.json() if joueurs_response.status_code == 200 else []
        
        # Créer un dictionnaire de joueurs pour accès rapide par ID
        # La structure peut être soit directe, soit avec un champ 'joueur' imbriqué
        joueurs_dict = {}
        for j in joueurs_data:
            if 'joueur' in j:
                # Structure avec joueur imbriqué
                joueur = j['joueur']
                joueurs_dict[joueur['id']] = joueur
            else:
                # Structure directe
                joueurs_dict[j['id']] = j
        
        # Calculer la taille du tableau (puissance de 2)
        nb_joueurs = len(joueurs_dict)
        taille_tableau = 1
        while taille_tableau < nb_joueurs:
            taille_tableau *= 2
        
        # Calculer le nombre de tours (log2 de la taille)
        nb_tours = int(math.log2(taille_tableau)) if taille_tableau > 0 else 1
        
        # Organiser les rencontres par tours en fonction du champ 'tour'
        rencontres_par_tour = {}
        for rencontre in rencontres:
            tour = rencontre.get('tour', 1)  # Par défaut tour 1
            if tour not in rencontres_par_tour:
                rencontres_par_tour[tour] = []
            rencontres_par_tour[tour].append(rencontre)
        
        # Trier les rencontres de chaque tour par position
        for tour in rencontres_par_tour:
            rencontres_par_tour[tour].sort(key=lambda r: r.get('position', 0))
        
        # Générer les noms de tours
        noms_tours = {}
        for i in range(1, nb_tours + 1):
            if i == nb_tours:
                noms_tours[i] = "Finale"
            elif i == nb_tours - 1:
                noms_tours[i] = "Demi-Finales"
            elif i == nb_tours - 2:
                noms_tours[i] = "Quarts de Finale"
            else:
                # 1/8, 1/16, 1/32...
                fraction = 2 ** (nb_tours - i + 1)
                noms_tours[i] = f"1/{fraction} de Finale"
        
        return render_template('rencontres/tableau_bracket.html',
                             evenement=evenement,
                             phase=phase,
                             rencontres=rencontres,
                             rencontres_par_tour=rencontres_par_tour,
                             joueurs_dict=joueurs_dict,
                             taille_tableau=taille_tableau,
                             nb_tours=nb_tours,
                             noms_tours=noms_tours)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_rencontres', evenement_id=evenement_id, phase_id=phase_id))

@app.route('/api/rencontres/<rencontre_id>/resultats', methods=['POST'])
def save_tableau_score(rencontre_id):
    """Sauvegarder les résultats d'un match de tableau avec auto-validation"""
    try:
        data = request.json
        resultats = data.get('resultats', [])
        
        if not resultats or len(resultats) != 2:
            return jsonify({'error': 'Il faut exactement 2 résultats'}), 400
        
        # Vérifier pas d'égalité
        scores = [r['points'] for r in resultats]
        if scores[0] == scores[1]:
            return jsonify({'error': 'Match nul impossible'}), 400
        
        # D'abord supprimer les anciens résultats s'ils existent
        try:
            requests.delete(f"{API_BASE_URL}/rencontres/{rencontre_id}/resultats")
        except:
            pass  # Ignore si pas de résultats existants
        
        # Envoyer chaque résultat individuellement à l'API backend
        for resultat in resultats:
            response = requests.post(
                f"{API_BASE_URL}/rencontres/{rencontre_id}/resultats",
                json=resultat
            )
            
            if response.status_code not in [200, 201]:
                return jsonify({'error': f'Erreur API: {response.text}'}), response.status_code
        
        return jsonify({'success': True, 'message': 'Score sauvegardé'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/evenements/<evenement_id>/phases/<phase_id>/tableau/generate-next-round', methods=['POST'])
def generate_next_round(evenement_id, phase_id):
    """Générer automatiquement le tour suivant du tableau"""
    try:
        current_tour = request.args.get('current_tour', type=int)
        if not current_tour:
            return jsonify({'error': 'current_tour manquant'}), 400
        
        response = requests.post(
            f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/tableau/generate-next-round",
            params={'current_tour': current_tour}
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Erreur API', 'details': response.text}), response.status_code
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/evenements/<evenement_id>/phases/<phase_id>/feuille-poule')
@app.route('/evenements/<evenement_id>/phases/<phase_id>/poules/<poule_id>/feuille-poule')
def view_feuille_poule(evenement_id, phase_id, poule_id=None):
    """Afficher la feuille de poule (mode saisie arbitre)"""
    try:
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        phase_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}")
        
        evenement = event_response.json() if event_response.status_code == 200 else {}
        phase = phase_response.json() if phase_response.status_code == 200 else {}
        
        # Récupérer les poules de cette phase
        poules_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/poules")
        all_poules = poules_response.json() if poules_response.status_code == 200 else []
        
        # Si un poule_id est fourni, ne garder que cette poule
        if poule_id:
            poules = [p for p in all_poules if p['id'] == poule_id]
            if not poules:
                flash("Poule non trouvée", "error")
                return redirect(url_for('view_rencontres', evenement_id=evenement_id, phase_id=phase_id))
        else:
            poules = all_poules
        
        # Si pas de poules, afficher tous les joueurs ensemble (ancien comportement)
        if not poules:
            # Récupérer les joueurs inscrits
            joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs")
            joueurs = joueurs_response.json() if joueurs_response.status_code == 200 else []
            poules = [{
                'id': None,
                'nom': 'Tous les joueurs',
                'ordre': 1,
                'joueurs': [{'id': j.get('joueur_id'), 'username': j.get('joueur', {}).get('username', 'N/A')} for j in joueurs]
            }]
        
        joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/joueurs")
        joueurs = joueurs_response.json() if joueurs_response.status_code == 200 else []
        
        # Récupérer toutes les rencontres avec résultats
        rencontres_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}/rencontres-complete")
        rencontres = rencontres_response.json() if rencontres_response.status_code == 200 else []
        
        # Récupérer tous les joueur_ids de toutes les poules
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        all_joueur_ids = set()
        for poule in poules:
            for joueur in poule.get('joueurs', []):
                all_joueur_ids.add(joueur.get('id'))
        
        # Récupérer les détails de tous les joueurs EN PARALLÈLE
        joueurs_details = {}
        
        def fetch_joueur(joueur_id):
            response = requests.get(f"{API_BASE_URL}/joueurs/{joueur_id}")
            if response.status_code == 200:
                return joueur_id, response.json()
            return joueur_id, None
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_joueur, jid): jid for jid in all_joueur_ids}
            for future in as_completed(futures):
                joueur_id, joueur_data = future.result()
                if joueur_data:
                    joueurs_details[joueur_id] = joueur_data
        
        # Construire UNE matrice PAR poule
        # matrices_by_poule[poule_id][joueur_i_id][joueur_j_id] = score de i contre j
        matrices_by_poule = {}
        
        for poule in poules:
            poule_id = poule.get('id')
            matrice_poule = {}
            
            # Initialiser la matrice pour cette poule
            for joueur in poule.get('joueurs', []):
                joueur_id = joueur.get('id')
                matrice_poule[joueur_id] = {}
            
            # Remplir la matrice avec les résultats de cette poule uniquement
            for rencontre in rencontres:
                # Ne traiter que les rencontres de cette poule
                if rencontre.get('poule_id') != poule_id:
                    continue
                    
                participants = rencontre.get('participants', [])
                resultats = rencontre.get('resultats', [])
                
                if len(participants) == 2 and len(resultats) >= 1:
                    # Créer un dict des résultats par participant
                    resultats_dict = {r['participant_id']: r for r in resultats}
                    
                    for participant_id in participants:
                        if participant_id in resultats_dict:
                            resultat = resultats_dict[participant_id]
                            # Trouver l'adversaire
                            adversaire_id = [p for p in participants if p != participant_id][0] if len(participants) == 2 else None
                            
                            if adversaire_id and participant_id in matrice_poule:
                                matrice_poule[participant_id][adversaire_id] = {
                                    'rencontre_id': rencontre['id'],
                                    'points': resultat.get('points'),
                                    'classement': resultat.get('classement')
                                }
            
            matrices_by_poule[poule_id if poule_id else 'default'] = matrice_poule
        
        # Calculer le classement provisoire
        classement = calculate_provisional_ranking(phase_id, joueurs)
        
        # Récupérer le max de points depuis la configuration de la phase
        configuration = phase.get('configuration', {})
        max_points = configuration.get('points_max')
        
        # Si pas dans configuration, essayer depuis le scoring
        if max_points is None:
            scoring = phase.get('scoring', {})
            if scoring.get('classement') and scoring['classement'].get('placeRanges'):
                # Trouver le max dans les placeRanges
                max_points = max([r['points'] for r in scoring['classement']['placeRanges']], default=15)
        
        # Par défaut 15 si rien n'est trouvé
        if max_points is None:
            max_points = 15
        
        return render_template('rencontres/feuille_poule.html',
                             evenement=evenement,
                             phase=phase,
                             poules=poules,
                             joueurs=joueurs,
                             joueurs_details=joueurs_details,
                             matrices_by_poule=matrices_by_poule,
                             classement=classement,
                             max_points=max_points)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_rencontres', evenement_id=evenement_id, phase_id=phase_id))

@app.route('/evenements/<evenement_id>/phases/<phase_id>/feuille-poule/save', methods=['POST'])
def save_feuille_poule_result(evenement_id, phase_id):
    """Proxy pour sauvegarder un résultat de feuille de poule (évite les problèmes CORS)"""
    try:
        data = request.get_json()
        
        # Appeler l'API backend
        response = requests.post(
            f"{API_BASE_URL}/phases/{phase_id}/feuille-poule/save-result",
            json=data
        )
        
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({"error": response.text}), response.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    """Voir les classements d'un événement - CALCUL DYNAMIQUE"""
    try:
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        evenement = event_response.json() if event_response.status_code == 200 else {}
        
        # Récupérer les phases
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        phases = phases_response.json() if phases_response.status_code == 200 else []
        
        # Pour chaque phase, calculer le classement provisoire dynamiquement
        phases_classements = []
        for phase in phases:
            joueurs_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase['id']}/joueurs")
            if joueurs_response.status_code == 200:
                joueurs = joueurs_response.json()
                classement = calculate_provisional_ranking(phase['id'], joueurs)
                
                phases_classements.append({
                    'phase': phase,
                    'classement': classement
                })
        
        return render_template('classements/view.html',
                             evenement=evenement,
                             phases_classements=phases_classements)
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_evenement', evenement_id=evenement_id))

# ============================================
# UTILITAIRES
# ============================================

def get_event_stats(evenement_id):
    """Récupérer les statistiques d'un événement - VERSION OPTIMISÉE"""
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
                
                # OPTIMISATION: Utiliser la route optimisée rencontres-complete
                rencontres_response = requests.get(f"{API_BASE_URL}/phases/{phase['id']}/rencontres-complete")
                if rencontres_response.status_code == 200:
                    rencontres = rencontres_response.json()
                    stats['total_rencontres'] += len(rencontres)
                    
                    # Les rencontres-complete incluent déjà les résultats !
                    for rencontre in rencontres:
                        if rencontre.get('resultats') and len(rencontre['resultats']) > 0:
                            stats['rencontres_terminees'] += 1
            
            stats['total_joueurs'] = len(joueurs_ids)
    except:
        pass
    
    return stats

def calculate_provisional_ranking(phase_id, joueurs_inscrits):
    """Calculer le classement provisoire d'une phase basé sur les résultats disponibles"""
    classement = {}
    
    try:
        # Récupérer la phase pour connaître le scoring
        phase_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}")
        if phase_response.status_code != 200:
            #print(f"DEBUG: Phase non trouvée - {phase_id}")
            return []
        
        phase = phase_response.json()
        scoring = phase.get('scoring', {})
        #print(f"DEBUG: Phase {phase.get('nom')} - Scoring: {scoring}")
        
        # Initialiser les scores pour tous les joueurs inscrits
        for joueur in joueurs_inscrits:
            joueur_id = joueur.get('joueur_id')
            classement[joueur_id] = {
                'joueur_id': joueur_id,
                'username': None,  # Sera rempli après
                'club': None,
                'points': 0,
                'victoires': 0,
                'defaites': 0,
                'nuls': 0,
                'rencontres_jouees': 0,
                'touches_donnees': 0,  # Pour l'indice
                'touches_recues': 0    # Pour l'indice
            }
        
        # Récupérer toutes les rencontres avec résultats
        rencontres_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}/rencontres-complete")
        if rencontres_response.status_code == 200:
            rencontres = rencontres_response.json()
            #print(f"DEBUG: {len(rencontres)} rencontres trouvées")
            
            for rencontre in rencontres:
                resultats = rencontre.get('resultats', [])
                #print(f"DEBUG: Rencontre {rencontre.get('id')[:8]}... - {len(resultats)} résultats")
                if resultats:
                    pass  # Log désactivé pour performance
                    #print(f"DEBUG: Résultats: {resultats}")
                
                if not resultats or len(resultats) < 2:
                    #print(f"DEBUG: Rencontre ignorée (pas assez de résultats)")
                    continue  # Pas de résultats ou incomplets
                
                # Traiter les résultats selon le type de scoring
                if scoring.get('match'):
                    # Scoring par match (victoire/nul/défaite)
                    points_match = scoring['match']
                    
                    if len(resultats) == 2:
                        r1, r2 = resultats[0], resultats[1]
                        
                        # Utiliser les points saisis pour déterminer le vainqueur
                        points_r1 = r1.get('points', 0) or 0
                        points_r2 = r2.get('points', 0) or 0
                        
                        # Comptabiliser les touches données et reçues
                        if r1['participant_id'] in classement:
                            classement[r1['participant_id']]['touches_donnees'] += points_r1
                            classement[r1['participant_id']]['touches_recues'] += points_r2
                        if r2['participant_id'] in classement:
                            classement[r2['participant_id']]['touches_donnees'] += points_r2
                            classement[r2['participant_id']]['touches_recues'] += points_r1
                        
                        #print(f"DEBUG: Match - {r1['participant_id'][:8]}: {points_r1} vs {r2['participant_id'][:8]}: {points_r2}")
                        
                        if points_r1 == points_r2:
                            # Match nul
                            #print(f"DEBUG: Match nul détecté")
                            if r1['participant_id'] in classement:
                                classement[r1['participant_id']]['points'] += points_match.get('nul', 1)
                                classement[r1['participant_id']]['nuls'] += 1
                                classement[r1['participant_id']]['rencontres_jouees'] += 1
                            if r2['participant_id'] in classement:
                                classement[r2['participant_id']]['points'] += points_match.get('nul', 1)
                                classement[r2['participant_id']]['nuls'] += 1
                                classement[r2['participant_id']]['rencontres_jouees'] += 1
                        elif points_r1 > points_r2:
                            # r1 gagne
                            #print(f"DEBUG: {r1['participant_id'][:8]} gagne")
                            if r1['participant_id'] in classement:
                                classement[r1['participant_id']]['points'] += points_match.get('victoire', 3)
                                classement[r1['participant_id']]['victoires'] += 1
                                classement[r1['participant_id']]['rencontres_jouees'] += 1
                            if r2['participant_id'] in classement:
                                classement[r2['participant_id']]['points'] += points_match.get('defaite', 0)
                                classement[r2['participant_id']]['defaites'] += 1
                                classement[r2['participant_id']]['rencontres_jouees'] += 1
                        else:
                            # r2 gagne
                            #print(f"DEBUG: {r2['participant_id'][:8]} gagne")
                            if r2['participant_id'] in classement:
                                classement[r2['participant_id']]['points'] += points_match.get('victoire', 3)
                                classement[r2['participant_id']]['victoires'] += 1
                                classement[r2['participant_id']]['rencontres_jouees'] += 1
                            if r1['participant_id'] in classement:
                                classement[r1['participant_id']]['points'] += points_match.get('defaite', 0)
                                classement[r1['participant_id']]['defaites'] += 1
                                classement[r1['participant_id']]['rencontres_jouees'] += 1
                
                elif scoring.get('classement'):
                    # Scoring par classement (placeRanges)
                    place_ranges = scoring['classement'].get('placeRanges', [])
                    
                    # Comptabiliser les touches et victoires pour tous les participants
                    if len(resultats) == 2:
                        r1, r2 = resultats[0], resultats[1]
                        points_r1 = r1.get('points', 0) or 0
                        points_r2 = r2.get('points', 0) or 0
                        
                        #print(f"DEBUG Classement - Match: {r1['participant_id'][:8]}: {points_r1} vs {r2['participant_id'][:8]}: {points_r2}")
                        
                        if r1['participant_id'] in classement:
                            classement[r1['participant_id']]['touches_donnees'] += points_r1
                            classement[r1['participant_id']]['touches_recues'] += points_r2
                            classement[r1['participant_id']]['rencontres_jouees'] += 1
                            
                            # Compter la victoire
                            if r1.get('classement') == 1:
                                classement[r1['participant_id']]['victoires'] += 1
                            elif r1.get('classement') == 2:
                                classement[r1['participant_id']]['defaites'] += 1
                            
                            #print(f"DEBUG {r1['participant_id'][:8]} - TD:{classement[r1['participant_id']]['touches_donnees']} TR:{classement[r1['participant_id']]['touches_recues']} V:{classement[r1['participant_id']]['victoires']}")
                        
                        if r2['participant_id'] in classement:
                            classement[r2['participant_id']]['touches_donnees'] += points_r2
                            classement[r2['participant_id']]['touches_recues'] += points_r1
                            classement[r2['participant_id']]['rencontres_jouees'] += 1
                            
                            # Compter la victoire
                            if r2.get('classement') == 1:
                                classement[r2['participant_id']]['victoires'] += 1
                            elif r2.get('classement') == 2:
                                classement[r2['participant_id']]['defaites'] += 1
                            
                            #print(f"DEBUG {r2['participant_id'][:8]} - TD:{classement[r2['participant_id']]['touches_donnees']} TR:{classement[r2['participant_id']]['touches_recues']} V:{classement[r2['participant_id']]['victoires']}")
                    
                    # Attribution des points selon les placeRanges
                    for resultat in resultats:
                        if resultat['participant_id'] not in classement:
                            continue
                        
                        place = resultat.get('classement')
                        if place:
                            # Trouver les points correspondant à la place
                            points_place = 0
                            for range_item in place_ranges:
                                if range_item['from'] <= place <= range_item['to']:
                                    points_place = range_item['points']
                                    break
                            
                            classement[resultat['participant_id']]['points'] += points_place
        
        # Récupérer les infos des joueurs EN PARALLÈLE
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        joueurs_ids = list(classement.keys())
        if joueurs_ids:
            def fetch_joueur_info(joueur_id):
                response = requests.get(f"{API_BASE_URL}/joueurs/{joueur_id}")
                if response.status_code == 200:
                    return joueur_id, response.json()
                return joueur_id, None
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(fetch_joueur_info, jid): jid for jid in joueurs_ids}
                for future in as_completed(futures):
                    joueur_id, joueur_data = future.result()
                    if joueur_data:
                        classement[joueur_id]['username'] = joueur_data.get('username', 'Inconnu')
                        classement[joueur_id]['club'] = joueur_data.get('club', '')
        
        # Calculer V/M (Victoires sur Matchs) et Indice pour chaque joueur
        for joueur_id in classement:
            rencontres_jouees = classement[joueur_id]['rencontres_jouees']
            if rencontres_jouees > 0:
                classement[joueur_id]['vm'] = classement[joueur_id]['victoires'] / rencontres_jouees
            else:
                classement[joueur_id]['vm'] = 0
            
            classement[joueur_id]['indice'] = classement[joueur_id]['touches_donnees'] - classement[joueur_id]['touches_recues']
        
        # Construire la clé de tri dynamiquement selon phase.scoring.ordrePriorite
        ordre_priorite = scoring.get('ordrePriorite', ['Points de Victoire', 'V/M', 'Indice (GoalAverage)', 'Points mis'])
        
        # Mapping des noms de critères vers les clés du dict
        critere_mapping = {
            'Points de Victoire': lambda x: -x['victoires'],
            'V/M': lambda x: -x['vm'],
            'Indice (GoalAverage)': lambda x: -x['indice'],
            'Points mis': lambda x: -x['touches_donnees'],
            'Points Pris': lambda x: -x['touches_recues']
        }
        
        # Construire le tuple de tri
        def build_sort_key(joueur):
            return tuple(critere_mapping.get(critere, lambda x: 0)(joueur) for critere in ordre_priorite)
        
        classement_list = sorted(classement.values(), key=build_sort_key)
        
        return classement_list
        
    except Exception as e:
        print(f"Erreur calcul classement: {e}")
        return []

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
    
    #print(f"DEBUG - Génération de {len(rencontres)} rencontres pour {len(joueurs_list)} joueurs")
    return rencontres

# ============================================
# LANCEMENT
# ============================================

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
