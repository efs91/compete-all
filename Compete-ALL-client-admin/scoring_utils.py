"""
Utilitaires pour traiter les données de scoring des phases
"""

def process_place_ranges(form_data):
    """
    Traite les plages de places depuis le formulaire
    
    Args:
        form_data: flask.request.form
        
    Returns:
        list: Liste de dictionnaires {from, to, points} triée par ordre croissant
    """
    place_ranges = []
    
    if 'range_from[]' in form_data:
        range_froms = form_data.getlist('range_from[]')
        range_tos = form_data.getlist('range_to[]')
        range_points_list = form_data.getlist('range_points[]')
        
        for i in range(len(range_froms)):
            if range_froms[i] and range_tos[i] and range_points_list[i]:
                from_place = int(range_froms[i])
                to_place = int(range_tos[i])
                points = int(range_points_list[i])
                
                # Validation: from doit être <= to
                if from_place > to_place:
                    raise ValueError(f"Place de début ({from_place}) ne peut pas être supérieure à la place de fin ({to_place})")
                
                place_ranges.append({
                    "from": from_place,
                    "to": to_place,
                    "points": points
                })
        
        # Trier les plages par ordre croissant
        place_ranges.sort(key=lambda x: x["from"])
        
        # Vérifier les chevauchements
        for i in range(len(place_ranges) - 1):
            if place_ranges[i]["to"] >= place_ranges[i + 1]["from"]:
                raise ValueError(f"Chevauchement détecté entre les plages: {place_ranges[i]['from']}-{place_ranges[i]['to']} et {place_ranges[i+1]['from']}-{place_ranges[i+1]['to']}")
    
    return place_ranges


def process_scoring_data(form_data):
    """
    Construit l'objet scoring complet depuis les données du formulaire
    
    Args:
        form_data: flask.request.form
        
    Returns:
        dict: Objet scoring avec classement, match, ordrePriorite, bonusPoints
    """
    # Plages de places pour le classement
    place_ranges = process_place_ranges(form_data)
    
    # Ordre de priorité pour départage
    ordre_priorite = [
        form_data.get('priorite_1', 'Points de Victoire'),
        form_data.get('priorite_2', 'Indice (GoalAverage)'),
        form_data.get('priorite_3', 'Points mis'),
        form_data.get('priorite_4', 'Points Pris')
    ]
    
    # Traiter les points bonus
    bonus_points = []
    if 'bonus_condition[]' in form_data:
        bonus_conditions = form_data.getlist('bonus_condition[]')
        bonus_points_values = form_data.getlist('bonus_points[]')
        
        for i in range(len(bonus_conditions)):
            if bonus_conditions[i] and bonus_points_values[i]:
                bonus_points.append({
                    "condition": bonus_conditions[i],
                    "points": int(bonus_points_values[i])
                })
    
    # Scoring pour classement (courses, groupes)
    scoring_classement = {
        "placeRanges": place_ranges,
        "lastPlaceZero": 'last_place_zero' in form_data
    }
    
    # Scoring pour matchs (victoire/nul/défaite)
    match_nul_possible = 'match_nul_possible' in form_data
    
    scoring_match = {
        "victoire": int(form_data.get('points_victoire') or 3),
        "defaite": int(form_data.get('points_defaite') or 0)
    }
    
    # N'ajouter le champ nul que si match nul possible
    if match_nul_possible:
        scoring_match["nul"] = int(form_data.get('points_nul') or 1)
    else:
        scoring_match["nul"] = 0  # Forcer à 0 si match nul impossible
    
    # Objet scoring complet
    scoring = {
        "classement": scoring_classement,
        "match": scoring_match,
        "ordrePriorite": ordre_priorite,
        "bonusPoints": bonus_points
    }
    
    return scoring
