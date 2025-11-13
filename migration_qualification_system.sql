-- Exécuter toutes les migrations pour le système de qualification

-- 1. Créer la table evenement_joueur
CREATE TABLE IF NOT EXISTS evenement_joueur (
    evenement_id VARCHAR(36) NOT NULL,
    joueur_id VARCHAR(36) NOT NULL,
    date_inscription DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (evenement_id, joueur_id),
    FOREIGN KEY (evenement_id) REFERENCES evenements(id) ON DELETE CASCADE,
    FOREIGN KEY (joueur_id) REFERENCES joueurs(id)
);

-- 2. Ajouter config_qualification à phase_evenement
ALTER TABLE phase_evenement 
ADD COLUMN config_qualification JSON NULL 
COMMENT 'Configuration de qualification: {mode: "par_poule"|"classement_phase"|"classement_general", nb_qualifies: X, criteres_tri: [...]}';

-- 3. Ajouter statut et phase_origine_id à phase_evenement_joueur
ALTER TABLE phase_evenement_joueur 
ADD COLUMN statut VARCHAR(50) NOT NULL DEFAULT 'inscrit' 
COMMENT 'inscrit, qualifie, elimine, repechage';

ALTER TABLE phase_evenement_joueur 
ADD COLUMN phase_origine_id VARCHAR(36) NULL 
COMMENT 'ID de la phase d''où vient la qualification (NULL si première phase)';
