"""Add phase instance ID to support multiple instances of same phase template

Revision ID: add_phase_instance_id
Revises: 5370cdbc07d9
Create Date: 2025-01-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
import uuid

# revision identifiers, used by Alembic.
revision = 'add_phase_instance_id'
down_revision = '5370cdbc07d9_recreate_joueurs_table'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Ajouter la colonne id à phase_evenement
    op.add_column('phase_evenement', sa.Column('id', sa.String(36), nullable=True))
    
    # 2. Générer des UUIDs pour les lignes existantes
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE phase_evenement 
        SET id = UUID()
        WHERE id IS NULL
    """))
    
    # 3. Rendre la colonne NOT NULL et PRIMARY KEY
    op.alter_column('phase_evenement', 'id', nullable=False)
    op.create_primary_key('pk_phase_evenement', 'phase_evenement', ['id'])
    
    # 4. Ajouter la colonne phase_instance_id à phase_evenement_joueur
    op.add_column('phase_evenement_joueur', sa.Column('phase_instance_id', sa.String(36), nullable=True))
    
    # 5. Migrer les données : mapper phase_id + evenement_id -> phase_instance_id
    connection.execute(sa.text("""
        UPDATE phase_evenement_joueur AS pej
        INNER JOIN phase_evenement AS pe 
            ON pej.phase_id = pe.phase_id 
            AND pej.evenement_id = pe.evenement_id
        SET pej.phase_instance_id = pe.id
    """))
    
    # 6. Supprimer l'ancienne colonne phase_id de phase_evenement_joueur
    op.drop_column('phase_evenement_joueur', 'phase_id')
    
    # 7. Rendre phase_instance_id NOT NULL et ajouter la foreign key
    op.alter_column('phase_evenement_joueur', 'phase_instance_id', nullable=False)
    op.create_foreign_key(
        'fk_pej_phase_instance', 
        'phase_evenement_joueur', 
        'phase_evenement', 
        ['phase_instance_id'], 
        ['id']
    )


def downgrade():
    # Remettre phase_id dans phase_evenement_joueur
    op.add_column('phase_evenement_joueur', sa.Column('phase_id', sa.String(36), nullable=True))
    
    # Récupérer les phase_id depuis phase_evenement
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE phase_evenement_joueur AS pej
        INNER JOIN phase_evenement AS pe ON pej.phase_instance_id = pe.id
        SET pej.phase_id = pe.phase_id
    """))
    
    op.alter_column('phase_evenement_joueur', 'phase_id', nullable=False)
    op.create_foreign_key(None, 'phase_evenement_joueur', 'phases', ['phase_id'], ['id'])
    
    # Supprimer phase_instance_id
    op.drop_constraint('fk_pej_phase_instance', 'phase_evenement_joueur', type_='foreignkey')
    op.drop_column('phase_evenement_joueur', 'phase_instance_id')
    
    # Supprimer l'id de phase_evenement
    op.drop_constraint('pk_phase_evenement', 'phase_evenement', type_='primary')
    op.drop_column('phase_evenement', 'id')
