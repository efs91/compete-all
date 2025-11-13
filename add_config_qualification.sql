-- Ajouter la colonne config_qualification à phase_evenement
ALTER TABLE phase_evenement 
ADD COLUMN config_qualification JSON NULL COMMENT 'Configuration de qualification: {mode: "par_poule"|"classement_phase"|"classement_general", nb_qualifies: X, criteres_tri: [...]}';
