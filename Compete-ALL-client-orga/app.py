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
        
        # Calculer le classement final de l'événement
        classement_final = calculate_event_final_ranking(evenement_id)
        
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
                             phases_classements=phases_classements,
                             classement_final=classement_final)
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

@app.route('/evenements/<evenement_id>/phases/<phase_id>/reinitialiser', methods=['POST'])
def reinitialiser_phase(evenement_id, phase_id):
    """Supprime toutes les rencontres et résultats d'une phase ET les recrée automatiquement"""
    try:
        # 1. Supprimer les rencontres/résultats
        response = requests.post(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/reinitialiser")
        
        if response.status_code != 200:
            flash(f"Erreur lors de la réinitialisation : {response.text}", "error")
            return redirect(url_for('view_rencontres', evenement_id=evenement_id, phase_id=phase_id))
        
        # 2. Recréer les rencontres automatiquement (appeler la progression)
        # Trouver la phase précédente pour faire la progression
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        
        if phases_response.status_code == 200:
            phases = phases_response.json()
            # Trouver l'index de la phase actuelle
            phase_index = next((i for i, p in enumerate(phases) if p['id'] == phase_id), None)
            
            if phase_index is not None and phase_index > 0:
                # Appeler la progression depuis la phase précédente
                phase_precedente = phases[phase_index - 1]
                progression_response = requests.post(
                    f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_precedente['id']}/progresser"
                )
                
                if progression_response.status_code == 200:
                    flash("✅ Phase réinitialisée et rencontres recréées avec succès !", "success")
                else:
                    flash(f"⚠️ Rencontres supprimées mais erreur lors de la recréation : {progression_response.text}", "warning")
            else:
                flash("✅ Rencontres supprimées. C'est la première phase, cliquez sur 'Lancer la compétition'.", "success")
        
        return redirect(url_for('view_rencontres', evenement_id=evenement_id, phase_id=phase_id))
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('view_rencontres', evenement_id=evenement_id, phase_id=phase_id))

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
        
        # Déterminer le classement à afficher
        type_general = phase.get('type_general', 'poule')
        if 'elimination' in type_general.lower() or 'bracket' in type_general.lower():
            # Pour un tableau, vérifier s'il a des résultats
            classement_tableau = calculate_provisional_ranking(phase_id, joueurs)
            a_des_resultats = any(j.get('rencontres_jouees', 0) > 0 for j in classement_tableau)
            
            if not a_des_resultats:
                # Tableau pas commencé : afficher le classement de la phase précédente
                phases_in_event_sorted = sorted(phases_in_event, key=lambda p: p.get('ordre') if p.get('ordre') is not None else 999)
                phase_idx = next((i for i, p in enumerate(phases_in_event_sorted) if p['id'] == phase_id), None)
                
                if phase_idx and phase_idx > 0:
                    phase_precedente = phases_in_event_sorted[phase_idx - 1]
                    joueurs_prec_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_precedente['id']}/joueurs")
                    if joueurs_prec_response.status_code == 200:
                        joueurs_prec = joueurs_prec_response.json()
                        classement = calculate_provisional_ranking(phase_precedente['id'], joueurs_prec)
                    else:
                        classement = classement_tableau
                else:
                    classement = classement_tableau
            else:
                classement = classement_tableau
        else:
            classement = calculate_provisional_ranking(phase_id, joueurs)
        
        # Détecter le type de phase pour afficher le bon mode
        type_general = phase.get('type_general', 'poule')
        
        # Filtrer les rencontres pour les tableaux : enlever les byes et matchs vides
        rencontres_filtrees = []
        if 'elimination' in type_general.lower() or 'bracket' in type_general.lower():
            # Calculer les noms des tours pour l'affichage
            import math
            
            # Trouver le tour maximum pour déterminer la taille du tableau
            max_tour = max([r.get('tour', 1) for r in rencontres], default=1)
            
            # Générer les noms de tours
            noms_tours = {}
            for i in range(1, max_tour + 1):
                if i == max_tour:
                    noms_tours[i] = "Finale"
                elif i == max_tour - 1:
                    noms_tours[i] = "Demi-Finale"
                elif i == max_tour - 2:
                    noms_tours[i] = "Quart de Finale"
                else:
                    # 1/8, 1/16, 1/32...
                    fraction = 2 ** (max_tour - i + 1)
                    noms_tours[i] = f"1/{fraction} de Finale"
            
            for rencontre in rencontres:
                participants = rencontre.get('participants', [])
                participants_details = rencontre.get('participants_details', [])
                
                # Ne pas afficher si aucun participant
                if not participants or len(participants) == 0:
                    continue
                
                # Ne pas afficher si un participant est None/null (adversaire pas encore connu)
                if None in participants or any(p is None for p in participants):
                    continue
                
                # Ne pas afficher si les détails contiennent "Inconnu"
                if participants_details:
                    if any(p.get('username') == 'Inconnu' for p in participants_details):
                        continue
                
                # Si un seul participant (bye), marquer comme bye
                if len(participants) == 1:
                    rencontre['is_bye'] = True
                    rencontre['bye_winner_id'] = participants[0]
                
                # Ajouter le nom du tour
                tour = rencontre.get('tour', 1)
                position = rencontre.get('position', 0)
                rencontre['nom_tour'] = f"{noms_tours.get(tour, f'Tour {tour}')} - Match {position + 1}"
                
                rencontres_filtrees.append(rencontre)
        else:
            rencontres_filtrees = rencontres
        
        return render_template('rencontres/list.html',
                             evenement=evenement,
                             phase=phase,
                             type_general=type_general,
                             rencontres=rencontres_filtrees,
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

@app.route('/api/rencontres/<rencontre_id>')
def get_rencontre(rencontre_id):
    """Récupérer les informations d'une rencontre"""
    try:
        response = requests.get(f"{API_BASE_URL}/rencontres/{rencontre_id}")
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({"error": "Rencontre non trouvée"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        
        # Utiliser l'endpoint optimisé bulk qui fait tout en une seule requête
        response = requests.put(
            f"{API_BASE_URL}/rencontres/{rencontre_id}/resultats/bulk",
            json=resultats,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            return jsonify({'success': True, 'message': 'Score sauvegardé'})
        else:
            return jsonify({'error': f'Erreur API: {response.text}'}), response.status_code
            
    except requests.Timeout:
        return jsonify({'error': 'Timeout lors de la sauvegarde'}), 504
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

@app.route('/evenements/<evenement_id>/phases/<phase_id>/classement')
def get_classement_poule(evenement_id, phase_id):
    """Récupérer le classement d'une poule en temps réel"""
    try:
        response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_id}/classement")
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
            
            # Construire la liste des résultats
            resultats_list = []
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
                
                resultats_list.append(resultat_data)
            
            # Utiliser l'endpoint bulk pour sauvegarder tous les résultats en une fois
            # Cela permettra la progression automatique dans les tableaux
            response = requests.put(
                f"{API_BASE_URL}/rencontres/{rencontre_id}/resultats/bulk",
                json=resultats_list
            )
            
            if response.status_code in [200, 201]:
                flash("Résultats enregistrés avec succès!", "success")
            else:
                flash(f"Erreur lors de l'enregistrement: {response.text}", "error")
            
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

def enrich_classement_with_phases(classement, phases, phases_classements, evenement_id):
    """Enrichit le classement avec le parcours du joueur dans toutes les phases
    
    Args:
        classement: Liste des joueurs classés (dernière phase)
        phases: Liste de toutes les phases de l'événement
        phases_classements: Dict {phase_id: classement_phase}
        evenement_id: ID de l'événement
        
    Returns:
        Liste enrichie avec parcours_phases pour chaque joueur
    """
    for entry in classement:
        joueur_id = entry.get('joueur_id')
        entry['parcours_phases'] = []
        
        # Pour chaque phase, chercher le résultat du joueur
        for phase in phases:
            phase_id = phase['id']
            phase_classement = phases_classements.get(phase_id, [])
            
            # Trouver le joueur dans cette phase
            joueur_dans_phase = next((j for j in phase_classement if j.get('joueur_id') == joueur_id), None)
            
            if joueur_dans_phase:
                # Déterminer le résultat selon le type de phase
                type_general = phase.get('type_general', '').lower()
                resultat = {
                    'phase_nom': phase.get('nom'),
                    'phase_type': type_general
                }
                
                if 'elimination' in type_general or 'bracket' in type_general:
                    # Tableau d'élimination
                    # Ne montrer vainqueur/finaliste que si les matchs sont joués
                    if joueur_dans_phase.get('rencontres_jouees', 0) > 0:
                        if joueur_dans_phase.get('est_vainqueur'):
                            resultat['texte'] = "Vainqueur"
                        elif joueur_dans_phase.get('position') == 2:
                            resultat['texte'] = "Finaliste"
                        elif joueur_dans_phase.get('position') == 3:
                            resultat['texte'] = "Demi-finaliste"
                        elif joueur_dans_phase.get('tour_sortie'):
                            tours_noms = ['', 'finale', 'demi-finale', 'quart de finale', '8ème de finale', '16ème de finale', '32ème de finale']
                            tour = joueur_dans_phase.get('tour_sortie')
                            if tour <= 6:
                                resultat['texte'] = f"Éliminé en {tours_noms[tour]}"
                            else:
                                resultat['texte'] = f"Éliminé (tour {tour})"
                        else:
                            resultat['texte'] = f"{joueur_dans_phase.get('position', '?')}ème"
                    else:
                        # Pas de matchs joués : afficher la position de qualification
                        position = joueur_dans_phase.get('rang_entree') or joueur_dans_phase.get('position', '?')
                        resultat['texte'] = f"Qualifié en position {position}"
                else:
                    # Poule ou course
                    position = phase_classement.index(joueur_dans_phase) + 1 if joueur_dans_phase in phase_classement else '?'
                    vm = joueur_dans_phase.get('vm', 0)
                    indice = joueur_dans_phase.get('indice', 0)
                    resultat['texte'] = f"{position}{'er' if position == 1 else 'ème'} (V/M={vm:.2f}, Indice={indice})"
                
                entry['parcours_phases'].append(resultat)
            else:
                # Joueur pas dans cette phase
                entry['parcours_phases'].append({
                    'phase_nom': phase.get('nom'),
                    'phase_type': '',
                    'texte': '-'
                })
    
    return classement


def calculate_event_final_ranking(evenement_id):
    """Calculer le classement final de l'événement avec le parcours complet
    
    Logique:
    - Si la dernière phase est un tableau d'élimination ET que la finale est jouée -> classement définitif
    - Sinon -> classement provisoire basé sur la dernière phase avec résultats
    - Pour chaque joueur, on ajoute son parcours dans TOUTES les phases
    
    Returns:
        dict avec 'classement', 'est_definitif', 'phases', 'phase_finale'
    """
    try:
        # Récupérer toutes les phases de l'événement, triées par ordre
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        if phases_response.status_code != 200:
            print(f"DEBUG: Pas de phases pour l'événement {evenement_id}")
            return {'classement': [], 'est_definitif': False, 'phases': [], 'phase_finale': None}
        
        phases = phases_response.json()
        if not phases:
            print(f"DEBUG: Liste de phases vide pour l'événement {evenement_id}")
            return {'classement': [], 'est_definitif': False, 'phases': [], 'phase_finale': None}
        
        print(f"DEBUG: {len(phases)} phases trouvées pour l'événement {evenement_id}")
        
        # Trier les phases par ordre (gérer les None)
        phases.sort(key=lambda p: p.get('ordre') if p.get('ordre') is not None else 999)
        
        # Calculer le classement de chaque phase
        phases_classements = {}
        for idx, phase in enumerate(phases):
            joueurs_phase_response = requests.get(
                f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase['id']}/joueurs"
            )
            if joueurs_phase_response.status_code == 200:
                joueurs_phase = joueurs_phase_response.json()
                
                # Si c'est un tableau et pas la première phase, passer le classement de la phase précédente
                classement_entree = None
                if idx > 0 and ('elimination' in phase.get('type_general', '').lower() or 'bracket' in phase.get('type_general', '').lower()):
                    phase_precedente = phases[idx - 1]
                    if phase_precedente['id'] in phases_classements:
                        classement_entree = phases_classements[phase_precedente['id']]
                
                classement_phase = calculate_provisional_ranking(phase['id'], joueurs_phase, classement_entree)
                phases_classements[phase['id']] = classement_phase
        
        # La dernière phase
        derniere_phase = phases[-1]
        type_general = derniere_phase.get('type_general', '').lower()
        print(f"DEBUG: Dernière phase = {derniere_phase.get('nom')}, type = {type_general}")
        
        # Récupérer les joueurs de la dernière phase
        joueurs_response = requests.get(
            f"{API_BASE_URL}/evenements/{evenement_id}/phases/{derniere_phase['id']}/joueurs"
        )
        joueurs = joueurs_response.json() if joueurs_response.status_code == 200 else []
        print(f"DEBUG: {len(joueurs)} joueurs dans la dernière phase")
        
        # Si c'est un tableau d'élimination directe
        if 'elimination' in type_general or 'bracket' in type_general:
            # Vérifier si la finale a été jouée
            rencontres_response = requests.get(
                f"{API_BASE_URL}/phases/{derniere_phase['id']}/rencontres-complete"
            )
            
            if rencontres_response.status_code == 200:
                rencontres = rencontres_response.json()
                
                # Trouver le tour maximum (finale)
                max_tour = max([r.get('tour', 1) for r in rencontres], default=1)
                
                # Chercher la finale avec des résultats
                finale = next(
                    (r for r in rencontres 
                     if r.get('tour') == max_tour 
                     and r.get('resultats') 
                     and len(r.get('resultats', [])) >= 2),
                    None
                )
                
                # Si la finale est jouée avec un résultat décisif
                if finale:
                    resultats_finale = finale.get('resultats', [])
                    if len(resultats_finale) >= 2:
                        points_r1 = resultats_finale[0].get('points', 0) or 0
                        points_r2 = resultats_finale[1].get('points', 0) or 0
                        
                        # Finale décisive = classement définitif
                        if points_r1 != points_r2:
                            print(f"DEBUG: Finale jouée avec résultat décisif! Calcul du classement définitif...")
                            # Calculer le classement d'entrée pour départager les ex-aequo
                            classement_entree = []
                            if len(phases) > 1:
                                # Prendre le classement de la phase précédente
                                phase_precedente = phases[-2]
                                joueurs_prec_response = requests.get(
                                    f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_precedente['id']}/joueurs"
                                )
                                if joueurs_prec_response.status_code == 200:
                                    joueurs_prec = joueurs_prec_response.json()
                                    classement_entree = calculate_provisional_ranking(phase_precedente['id'], joueurs_prec)
                            
                            classement = calculate_bracket_ranking(
                                derniere_phase['id'], 
                                joueurs,
                                classement_entree
                            )
                            
                            # Enrichir le classement avec le parcours dans toutes les phases
                            classement = enrich_classement_with_phases(classement, phases, phases_classements, evenement_id)
                            
                            return {
                                'classement': classement,
                                'est_definitif': True,
                                'phases': phases,
                                'phase_finale': derniere_phase
                            }
        
        # Classement provisoire : 
        # Si c'est un tableau sans résultats, utiliser le classement de la phase précédente
        if ('elimination' in type_general or 'bracket' in type_general):
            # Récupérer le classement d'entrée (phase précédente)
            classement_entree = None
            if len(phases) > 1:
                phase_precedente = phases[-2]
                if phase_precedente['id'] in phases_classements:
                    classement_entree = phases_classements[phase_precedente['id']]
            
            # Vérifier si le tableau a des résultats
            classement_tableau = calculate_provisional_ranking(derniere_phase['id'], joueurs, classement_entree)
            a_des_resultats = any(j.get('rencontres_jouees', 0) > 0 for j in classement_tableau)
            
            if not a_des_resultats and len(phases) > 1:
                # Tableau pas commencé, utiliser la phase précédente pour le classement général
                print(f"DEBUG: Tableau pas commencé, utilisation de la phase précédente")
                classement = phases_classements[phases[-2]['id']]
            else:
                classement = classement_tableau
        else:
            classement = calculate_provisional_ranking(derniere_phase['id'], joueurs)
        
        print(f"DEBUG: Classement provisoire calculé - {len(classement)} joueurs")
        
        # Enrichir le classement avec le parcours dans toutes les phases
        classement = enrich_classement_with_phases(classement, phases, phases_classements, evenement_id)
        
        return {
            'classement': classement,
            'est_definitif': False,
            'phases': phases,
            'phase_finale': derniere_phase
        }
        
    except Exception as e:
        print(f"Erreur calcul classement final: {e}")
        import traceback
        traceback.print_exc()
        return {'classement': [], 'est_definitif': False, 'phase_finale': None}


@app.route('/evenements/<evenement_id>/classements')
def view_classements(evenement_id):
    """Voir les classements d'un événement - CALCUL DYNAMIQUE"""
    try:
        event_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}")
        evenement = event_response.json() if event_response.status_code == 200 else {}
        
        # Récupérer les phases
        phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
        phases = phases_response.json() if phases_response.status_code == 200 else []
        
        # Calculer le classement final de l'événement
        classement_final = calculate_event_final_ranking(evenement_id)
        
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
                             phases_classements=phases_classements,
                             classement_final=classement_final)
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

def calculate_bracket_ranking(phase_id, joueurs_inscrits, classement_entree):
    """Calculer le classement pour un tableau d'élimination directe
    
    Args:
        phase_id: ID de la phase (tableau)
        joueurs_inscrits: Liste des joueurs inscrits au tableau
        classement_entree: Classement provisoire avant le tableau (pour départager les ex-aequo)
    
    Returns:
        Liste de joueurs classés selon leur tour de sortie
    """
    try:
        # Récupérer toutes les rencontres du tableau avec leurs résultats
        rencontres_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}/rencontres-complete")
        if rencontres_response.status_code != 200:
            return []
        
        rencontres = rencontres_response.json()
        
        # Initialiser le classement avec tous les joueurs
        classement = {}
        for joueur in joueurs_inscrits:
            joueur_id = joueur.get('joueur_id')
            classement[joueur_id] = {
                'joueur_id': joueur_id,
                'username': None,
                'club': None,
                'tour_sortie': 0,  # Tour où le joueur est éliminé (0 = pas encore éliminé)
                'est_vainqueur': False,
                'rang_entree': 0,  # Pour départager les ex-aequo
                'position': 0,
                # Champs pour compatibilité avec calculate_provisional_ranking
                'points': 0,
                'victoires': 0,
                'defaites': 0,
                'nuls': 0,
                'rencontres_jouees': 0,
                'touches_donnees': 0,
                'touches_recues': 0,
                'vm': 0,
                'indice': 0
            }
        
        # Trouver le rang d'entrée de chaque joueur depuis le classement d'entrée
        if classement_entree:
            for idx, entry in enumerate(classement_entree):
                joueur_id = entry.get('joueur_id')
                if joueur_id and joueur_id in classement:
                    classement[joueur_id]['rang_entree'] = idx + 1
        
        # Si pas de classement d'entrée, utiliser l'ordre d'inscription ou seed
        if not classement_entree:
            for joueur in joueurs_inscrits:
                joueur_id = joueur.get('joueur_id')
                if joueur_id in classement:
                    classement[joueur_id]['rang_entree'] = joueur.get('seed', 999) or joueur.get('ordre_inscription', 999) or 999
        
        # Trouver le tour maximum (finale)
        max_tour = max([r.get('tour', 1) for r in rencontres], default=1)
        
        # Analyser chaque rencontre pour déterminer les éliminés
        for rencontre in rencontres:
            resultats = rencontre.get('resultats', [])
            if not resultats or len(resultats) < 2:
                continue
            
            tour = rencontre.get('tour', 1)
            
            # Déterminer le vainqueur et le perdant
            r1, r2 = resultats[0], resultats[1]
            points_r1 = r1.get('points', 0) or 0
            points_r2 = r2.get('points', 0) or 0
            
            # Comptabiliser les statistiques
            if r1['participant_id'] in classement:
                classement[r1['participant_id']]['rencontres_jouees'] += 1
                classement[r1['participant_id']]['touches_donnees'] += points_r1
                classement[r1['participant_id']]['touches_recues'] += points_r2
            
            if r2['participant_id'] in classement:
                classement[r2['participant_id']]['rencontres_jouees'] += 1
                classement[r2['participant_id']]['touches_donnees'] += points_r2
                classement[r2['participant_id']]['touches_recues'] += points_r1
            
            # Le perdant est éliminé à ce tour (si pas déjà marqué à un tour supérieur)
            if points_r1 > points_r2:
                # r2 perd
                if r2['participant_id'] in classement:
                    if classement[r2['participant_id']]['tour_sortie'] == 0:
                        classement[r2['participant_id']]['tour_sortie'] = tour
                    classement[r2['participant_id']]['defaites'] += 1
                # r1 gagne
                if r1['participant_id'] in classement:
                    classement[r1['participant_id']]['victoires'] += 1
                    # Si c'est la finale, r1 est le vainqueur
                    if tour == max_tour:
                        classement[r1['participant_id']]['est_vainqueur'] = True
            elif points_r2 > points_r1:
                # r1 perd
                if r1['participant_id'] in classement:
                    if classement[r1['participant_id']]['tour_sortie'] == 0:
                        classement[r1['participant_id']]['tour_sortie'] = tour
                    classement[r1['participant_id']]['defaites'] += 1
                # r2 gagne
                if r2['participant_id'] in classement:
                    classement[r2['participant_id']]['victoires'] += 1
                    # Si c'est la finale, r2 est le vainqueur
                    if tour == max_tour:
                        classement[r2['participant_id']]['est_vainqueur'] = True
            else:
                # Match nul
                if r1['participant_id'] in classement:
                    classement[r1['participant_id']]['nuls'] += 1
                if r2['participant_id'] in classement:
                    classement[r2['participant_id']]['nuls'] += 1
        
        # Calculer V/M et indice pour chaque joueur
        for joueur_id in classement:
            rencontres_jouees = classement[joueur_id]['rencontres_jouees']
            if rencontres_jouees > 0:
                classement[joueur_id]['vm'] = classement[joueur_id]['victoires'] / rencontres_jouees
            else:
                classement[joueur_id]['vm'] = 0
            
            classement[joueur_id]['indice'] = classement[joueur_id]['touches_donnees'] - classement[joueur_id]['touches_recues']
        
        # Récupérer les infos des joueurs
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def fetch_joueur_info(joueur_id):
            response = requests.get(f"{API_BASE_URL}/joueurs/{joueur_id}")
            if response.status_code == 200:
                return joueur_id, response.json()
            return joueur_id, None
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_joueur_info, jid): jid for jid in classement.keys()}
            for future in as_completed(futures):
                joueur_id, joueur_data = future.result()
                if joueur_data:
                    classement[joueur_id]['username'] = joueur_data.get('username', 'Inconnu')
                    classement[joueur_id]['club'] = joueur_data.get('club', '')
        
        # Calculer le classement final selon les règles
        classement_list = []
        
        # 1. Le vainqueur de la finale est 1er
        vainqueur = [j for j in classement.values() if j['est_vainqueur']]
        if vainqueur:
            vainqueur[0]['position'] = 1
            classement_list.append(vainqueur[0])
        
        # 2. Le perdant de la finale est 2ème
        perdant_finale = [j for j in classement.values() if j['tour_sortie'] == max_tour and not j['est_vainqueur']]
        if perdant_finale:
            perdant_finale[0]['position'] = 2
            classement_list.append(perdant_finale[0])
        
        # 3. Pour chaque tour, classer les perdants
        # RÈGLE SPÉCIALE : Les 2 perdants de demi-finale sont 3ème ex-aequo
        # Pour les autres tours : classés selon leur rang d'entrée
        # Exemple: perdants de quart → positions 5, 6, 7, 8 selon leur classement d'entrée
        for tour in range(max_tour - 1, 0, -1):
            perdants_tour = [j for j in classement.values() if j['tour_sortie'] == tour]
            
            if perdants_tour:
                # Trier par rang d'entrée (meilleur seed = meilleure position)
                perdants_tour.sort(key=lambda x: x.get('rang_entree') or 999)
                
                # Calculer la position de départ pour ce tour
                # Demi-finale (max_tour - 1) : position de départ 3
                # Quart (max_tour - 2) : position de départ 5
                # 8ème (max_tour - 3) : position de départ 9
                position_debut = 2 ** (max_tour - tour) + 1
                
                # CAS SPÉCIAL : Les perdants de demi-finale sont EX-AEQUO à la 3ème place
                if tour == max_tour - 1:
                    # Demi-finales : tous 3ème ex-aequo
                    for joueur in perdants_tour:
                        joueur['position'] = 3
                        classement_list.append(joueur)
                else:
                    # Autres tours : classement selon rang d'entrée
                    for idx, joueur in enumerate(perdants_tour):
                        joueur['position'] = position_debut + idx
                        classement_list.append(joueur)
        
        # 4. Les joueurs pas encore éliminés (pas de résultats) sont classés après
        non_elimines = [j for j in classement.values() if j['tour_sortie'] == 0 and not j['est_vainqueur']]
        if non_elimines:
            non_elimines.sort(key=lambda x: x.get('rang_entree') or 999)
            position_suivante = len(classement_list) + 1
            for joueur in non_elimines:
                joueur['position'] = position_suivante
                classement_list.append(joueur)
                position_suivante += 1
        
        return classement_list
        
    except Exception as e:
        print(f"Erreur calcul classement bracket: {e}")
        return []


def calculate_provisional_ranking(phase_id, joueurs_inscrits, classement_entree=None):
    """Calculer le classement provisoire d'une phase basé sur les résultats disponibles
    
    Args:
        phase_id: ID de la phase
        joueurs_inscrits: Liste des joueurs inscrits
        classement_entree: Classement de la phase précédente (pour les tableaux)
    """
    classement = {}
    
    try:
        # Récupérer la phase pour connaître le scoring
        phase_response = requests.get(f"{API_BASE_URL}/phases/{phase_id}")
        if phase_response.status_code != 200:
            #print(f"DEBUG: Phase non trouvée - {phase_id}")
            return []
        
        phase = phase_response.json()
        type_general = phase.get('type_general', '')
        scoring = phase.get('scoring', {})
        #print(f"DEBUG: Phase {phase.get('nom')} - Scoring: {scoring}")
        
        # Si c'est un tableau d'élimination, utiliser la fonction spécifique
        if type_general and 'elimination' in type_general.lower():
            # Pour un tableau, on a besoin du classement d'entrée
            # Si pas fourni, essayer de le récupérer depuis l'événement
            if not classement_entree:
                # Trouver l'événement de cette phase
                evenement_id = phase.get('evenement_id')
                if evenement_id:
                    phases_response = requests.get(f"{API_BASE_URL}/evenements/{evenement_id}/phases")
                    if phases_response.status_code == 200:
                        phases = phases_response.json()
                        phases.sort(key=lambda p: p.get('ordre') if p.get('ordre') is not None else 999)
                        
                        # Trouver l'index de la phase actuelle
                        phase_actuelle_idx = next((i for i, p in enumerate(phases) if p['id'] == phase_id), None)
                        
                        # Si c'est pas la première phase, récupérer le classement de la phase précédente
                        if phase_actuelle_idx and phase_actuelle_idx > 0:
                            phase_precedente = phases[phase_actuelle_idx - 1]
                            joueurs_prec_response = requests.get(
                                f"{API_BASE_URL}/evenements/{evenement_id}/phases/{phase_precedente['id']}/joueurs"
                            )
                            if joueurs_prec_response.status_code == 200:
                                joueurs_prec = joueurs_prec_response.json()
                                classement_entree = calculate_provisional_ranking(phase_precedente['id'], joueurs_prec)
            
            return calculate_bracket_ranking(phase_id, joueurs_inscrits, classement_entree or [])
        
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
