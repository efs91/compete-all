-- Ajouter la colonne ordre à la table phase_evenement
ALTER TABLE phase_evenement 
ADD COLUMN ordre INT NOT NULL DEFAULT 0;

-- Initialiser l'ordre pour chaque événement selon l'ordre d'insertion
SET @row_number = 0;
SET @current_event = '';

UPDATE phase_evenement pe
INNER JOIN (
    SELECT 
        phase_id,
        evenement_id,
        @row_number := IF(@current_event = evenement_id, @row_number + 1, 1) AS new_ordre,
        @current_event := evenement_id
    FROM phase_evenement
    ORDER BY evenement_id, phase_id
) AS numbered ON pe.phase_id = numbered.phase_id AND pe.evenement_id = numbered.evenement_id
SET pe.ordre = numbered.new_ordre;
