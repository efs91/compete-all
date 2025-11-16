-- Ajouter les colonnes tour et position à la table rencontres
-- tour: numéro du tour dans le bracket (1 = premier tour, 2 = demi, 3 = finale, etc.)
-- position: position du match dans le tour (pour l'ordre d'affichage)

ALTER TABLE rencontres 
ADD COLUMN tour INT DEFAULT 1,
ADD COLUMN position INT DEFAULT 0;

-- Mettre à jour les rencontres existantes
-- Par défaut, tout est au tour 1, position 0
-- Les matchs de poules restent à tour=1, position sera utilisé seulement pour les tableaux
