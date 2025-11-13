from app.database import engine
from sqlalchemy import text

try:
    with engine.connect() as connection:
        print("Ajout de la colonne ordre à phase_evenement...")
        
        # Ajouter la colonne ordre
        connection.execute(text("""
            ALTER TABLE phase_evenement 
            ADD COLUMN ordre INT NOT NULL DEFAULT 0
        """))
        connection.commit()
        print("✓ Colonne ordre ajoutée")
        
        print("\nInitialisation de l'ordre pour chaque événement...")
        
        # Récupérer tous les événements
        evenements = connection.execute(text("SELECT DISTINCT evenement_id FROM phase_evenement")).fetchall()
        
        for (evenement_id,) in evenements:
            # Récupérer les phases de cet événement
            phases = connection.execute(text("""
                SELECT phase_id FROM phase_evenement 
                WHERE evenement_id = :evenement_id
                ORDER BY phase_id
            """), {"evenement_id": evenement_id}).fetchall()
            
            # Mettre à jour l'ordre
            for idx, (phase_id,) in enumerate(phases, 1):
                connection.execute(text("""
                    UPDATE phase_evenement 
                    SET ordre = :ordre 
                    WHERE phase_id = :phase_id AND evenement_id = :evenement_id
                """), {"ordre": idx, "phase_id": phase_id, "evenement_id": evenement_id})
            
            print(f"✓ Événement {evenement_id}: {len(phases)} phases ordonnées")
        
        connection.commit()
        print("\n✅ Migration terminée avec succès !")
        
except Exception as e:
    print(f"❌ Erreur : {str(e)}")
