-- Migration pour ajouter le système de poules

-- 1. Créer la table poules
CREATE TABLE IF NOT EXISTS poules (
    id VARCHAR(36) PRIMARY KEY,
    phase_id VARCHAR(36) NOT NULL,
    evenement_id VARCHAR(36) NOT NULL,
    nom VARCHAR(100) NOT NULL,
    ordre INT NOT NULL DEFAULT 1,
    FOREIGN KEY (phase_id) REFERENCES phases(id) ON DELETE CASCADE,
    FOREIGN KEY (evenement_id) REFERENCES evenements(id) ON DELETE CASCADE
);

-- 2. Créer la table d'association poule_joueur
CREATE TABLE IF NOT EXISTS poule_joueur (
    poule_id VARCHAR(36) NOT NULL,
    joueur_id VARCHAR(36) NOT NULL,
    ordre INT NULL,
    PRIMARY KEY (poule_id, joueur_id),
    FOREIGN KEY (poule_id) REFERENCES poules(id) ON DELETE CASCADE,
    FOREIGN KEY (joueur_id) REFERENCES joueurs(id) ON DELETE CASCADE
);

-- 3. Ajouter une colonne poule_id aux rencontres (optionnel, pour tracer quelle rencontre appartient à quelle poule)
ALTER TABLE rencontres 
ADD COLUMN poule_id VARCHAR(36) NULL,
ADD FOREIGN KEY (poule_id) REFERENCES poules(id) ON DELETE SET NULL;
