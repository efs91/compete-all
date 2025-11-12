"""recreate joueurs table

Revision ID: 5370cdbc07d9
Revises: 
Create Date: 2024-03-09 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '5370cdbc07d9'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Sauvegarder les données existantes si nécessaire
    try:
        # Créer une table temporaire pour la sauvegarde
        op.execute("""
            CREATE TABLE joueurs_backup AS 
            SELECT id, nom as username, prenom, email, telephone 
            FROM joueurs
        """)
    except Exception as e:
        print(f"Pas de données à sauvegarder ou erreur : {str(e)}")

    # Supprimer les contraintes de clé étrangère qui référencent joueurs
    try:
        op.drop_constraint('phase_joueur_ibfk_2', 'phase_joueur', type_='foreignkey')
        op.drop_constraint('equipe_joueur_ibfk_2', 'equipe_joueur', type_='foreignkey')
        op.drop_constraint('points_classement_ibfk_2', 'points_classement', type_='foreignkey')
    except Exception as e:
        print(f"Erreur lors de la suppression des contraintes : {str(e)}")

    # Supprimer la table joueurs
    op.drop_table('joueurs')

    # Créer la nouvelle table joueurs
    op.create_table('joueurs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(255), nullable=False, unique=True),
        sa.Column('prenom', sa.String(255), nullable=True),
        sa.Column('nom', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('date_naissance', sa.DateTime(), nullable=True),
        sa.Column('telephone', sa.String(20), nullable=True),
        sa.Column('users_ingame', sa.JSON(), nullable=True),
        sa.Column('user_discord', sa.String(255), nullable=True),
        sa.Column('classements', sa.JSON(), nullable=True),
        sa.Column('nation', sa.String(255), nullable=True),
        sa.Column('club', sa.String(255), nullable=True),
        sa.Column('status', sa.String(255), nullable=True),
        sa.Column('comment', sa.String(1000), nullable=True)
    )

    # Recréer les contraintes de clé étrangère
    op.create_foreign_key('phase_joueur_ibfk_2', 'phase_joueur', 'joueurs', ['joueur_id'], ['id'])
    op.create_foreign_key('equipe_joueur_ibfk_2', 'equipe_joueur', 'joueurs', ['joueur_id'], ['id'])
    op.create_foreign_key('points_classement_ibfk_2', 'points_classement', 'joueurs', ['joueur_id'], ['id'])

    # Restaurer les données si la sauvegarde existe
    try:
        op.execute("""
            INSERT INTO joueurs (id, username, prenom, email, telephone)
            SELECT id, username, prenom, email, telephone
            FROM joueurs_backup
        """)
        # Supprimer la table de sauvegarde
        op.execute("DROP TABLE joueurs_backup")
    except Exception as e:
        print(f"Pas de données à restaurer ou erreur : {str(e)}")

def downgrade() -> None:
    # Supprimer les contraintes de clé étrangère
    op.drop_constraint('phase_joueur_ibfk_2', 'phase_joueur', type_='foreignkey')
    op.drop_constraint('equipe_joueur_ibfk_2', 'equipe_joueur', type_='foreignkey')
    op.drop_constraint('points_classement_ibfk_2', 'points_classement', type_='foreignkey')

    # Supprimer la nouvelle table
    op.drop_table('joueurs')

    # Recréer l'ancienne table
    op.create_table('joueurs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('prenom', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('telephone', sa.String(20), nullable=True)
    )

    # Recréer les contraintes de clé étrangère
    op.create_foreign_key('phase_joueur_ibfk_2', 'phase_joueur', 'joueurs', ['joueur_id'], ['id'])
    op.create_foreign_key('equipe_joueur_ibfk_2', 'equipe_joueur', 'joueurs', ['joueur_id'], ['id'])
    op.create_foreign_key('points_classement_ibfk_2', 'points_classement', 'joueurs', ['joueur_id'], ['id'])

    # Restaurer les données de la sauvegarde si elle existe
    try:
        op.execute("""
            INSERT INTO joueurs (id, nom, prenom, email, telephone)
            SELECT id, username, prenom, email, telephone
            FROM joueurs_backup
        """)
        op.execute("DROP TABLE joueurs_backup")
    except Exception as e:
        print(f"Pas de données à restaurer ou erreur : {str(e)}")
