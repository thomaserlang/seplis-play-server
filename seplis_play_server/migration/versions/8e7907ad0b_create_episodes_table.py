"""create episodes table

Revision ID: 8e7907ad0b
Revises: None
Create Date: 2014-11-09 13:09:30.912736

"""

# revision identifiers, used by Alembic.
revision = '8e7907ad0b'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('episodes', 
        sa.Column('series_id', sa.Integer, primary_key=True),
        sa.Column('number', sa.Integer),
        sa.Column('path', sa.String(400), primary_key=True),
        sa.Column('metadata', sa.JSON),
        sa.Column('modified_time', sa.DateTime),
    )

    op.create_table('episode_number_lookup', 
        sa.Column('series_id', sa.Integer, primary_key=True),
        sa.Column('lookup_type', sa.Integer, primary_key=True),
        sa.Column('lookup_value', sa.String(45), primary_key=True),        
        sa.Column('number', sa.Integer)
    )

    op.create_table('series_id_lookup', 
        sa.Column('file_title', sa.String(200), primary_key=True),
        sa.Column('series_title', sa.String(200)),
        sa.Column('series_id', sa.Integer),
        sa.Column('updated_at', sa.DateTime),
    )

def downgrade():
    raise NotImplemented
