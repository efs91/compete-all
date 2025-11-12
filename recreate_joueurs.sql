-- Suppression des contraintes de clé étrangère
ALTER TABLE phase_joueur DROP FOREIGN KEY phase_joueur_ibfk_2;
ALTER TABLE equipe_joueur DROP FOREIGN KEY equipe_joueur_ibfk_2;
ALTER TABLE points_classement DROP FOREIGN KEY points_classement_ibfk_2;

-- Suppression de la table joueurs
DROP TABLE IF EXISTS joueurs;

-- Création de la nouvelle table joueurs
CREATE TABLE joueurs (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    prenom VARCHAR(255),
    nom VARCHAR(255),
    email VARCHAR(255),
    date_naissance DATETIME,
    telephone VARCHAR(20),
    users_ingame JSON,
    user_discord VARCHAR(255),
    classements JSON,
    nation VARCHAR(255),
    club VARCHAR(255),
    status VARCHAR(255),
    comment VARCHAR(1000)
);

-- Recréation des contraintes de clé étrangère
ALTER TABLE phase_joueur 
ADD CONSTRAINT phase_joueur_ibfk_2 
FOREIGN KEY (joueur_id) REFERENCES joueurs(id);

ALTER TABLE equipe_joueur 
ADD CONSTRAINT equipe_joueur_ibfk_2 
FOREIGN KEY (joueur_id) REFERENCES joueurs(id);

ALTER TABLE points_classement 
ADD CONSTRAINT points_classement_ibfk_2 
FOREIGN KEY (joueur_id) REFERENCES joueurs(id); 