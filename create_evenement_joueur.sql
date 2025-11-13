-- Créer la table evenement_joueur pour les inscriptions globales
CREATE TABLE evenement_joueur (
    evenement_id VARCHAR(36) NOT NULL,
    joueur_id VARCHAR(36) NOT NULL,
    date_inscription DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (evenement_id, joueur_id),
    FOREIGN KEY (evenement_id) REFERENCES evenements(id) ON DELETE CASCADE,
    FOREIGN KEY (joueur_id) REFERENCES joueurs(id)
);
