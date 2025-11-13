-- Ajouter les colonnes statut et phase_origine_id à phase_evenement_joueur
ALTER TABLE phase_evenement_joueur 
ADD COLUMN statut VARCHAR(50) NOT NULL DEFAULT 'inscrit' COMMENT 'inscrit, qualifie, elimine, repechage';

ALTER TABLE phase_evenement_joueur 
ADD COLUMN phase_origine_id VARCHAR(36) NULL COMMENT 'ID de la phase d''où vient la qualification (NULL si première phase)';
