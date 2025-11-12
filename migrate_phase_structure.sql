-- Sauvegarde des données actuelles avant de modifier la structure
CREATE TABLE IF NOT EXISTS phase_joueur_backup AS
SELECT * FROM phase_joueur;

CREATE TABLE IF NOT EXISTS phases_backup AS 
SELECT * FROM phases;

-- Création des nouvelles tables de liaison
CREATE TABLE IF NOT EXISTS phase_evenement (
    phase_id VARCHAR(36) NOT NULL,
    evenement_id VARCHAR(36) NOT NULL,
    PRIMARY KEY (phase_id, evenement_id),
    FOREIGN KEY (phase_id) REFERENCES phases(id),
    FOREIGN KEY (evenement_id) REFERENCES evenements(id)
);

CREATE TABLE IF NOT EXISTS phase_evenement_joueur (
    phase_id VARCHAR(36) NOT NULL,
    evenement_id VARCHAR(36) NOT NULL,
    joueur_id VARCHAR(36) NOT NULL,
    ordre_inscription INT NOT NULL,
    seed INT NULL,
    PRIMARY KEY (phase_id, evenement_id, joueur_id),
    FOREIGN KEY (phase_id) REFERENCES phases(id),
    FOREIGN KEY (evenement_id) REFERENCES evenements(id),
    FOREIGN KEY (joueur_id) REFERENCES joueurs(id)
);

-- Migration des données phases-joueurs vers la nouvelle structure
INSERT INTO phase_evenement (phase_id, evenement_id)
SELECT p.id, p.evenement_id FROM phases p
WHERE p.evenement_id IS NOT NULL;

INSERT INTO phase_evenement_joueur (phase_id, evenement_id, joueur_id, ordre_inscription, seed)
SELECT pj.phase_id, p.evenement_id, pj.joueur_id, pj.ordre_inscription, pj.seed 
FROM phase_joueur pj
JOIN phases p ON pj.phase_id = p.id
WHERE p.evenement_id IS NOT NULL;

-- Modification de la table rencontres pour ajouter evenement_id
ALTER TABLE rencontres ADD COLUMN evenement_id VARCHAR(36);
UPDATE rencontres r SET evenement_id = (
    SELECT p.evenement_id FROM phases p WHERE p.id = r.phase_id
);
ALTER TABLE rencontres MODIFY evenement_id VARCHAR(36) NOT NULL;
ALTER TABLE rencontres ADD FOREIGN KEY (evenement_id) REFERENCES evenements(id);

-- Suppression de la contrainte et du champ evenement_id de la table phases
-- Attention: enlever les contraintes de clé étrangère d'abord
ALTER TABLE phases DROP FOREIGN KEY phases_ibfk_3; -- Ajuster le nom de la contrainte si nécessaire

-- Puis supprimer la colonne
ALTER TABLE phases DROP COLUMN evenement_id;

-- Mise à jour des autres tables/relations si nécessaire

-- Suppression de l'ancienne table phase_joueur
DROP TABLE phase_joueur; 