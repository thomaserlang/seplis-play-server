"""Movies

Revision ID: 9fbe5febc089
Revises: 8e7907ad0b
Create Date: 2022-06-26 23:07:14.494469

"""

# revision identifiers, used by Alembic.
revision = '9fbe5febc089'
down_revision = '8e7907ad0b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('movie_id_lookup', 
        sa.Column('file_title', sa.String(200), primary_key=True),
        sa.Column('movie_title', sa.String(200)),
        sa.Column('movie_id', sa.Integer),
        sa.Column('updated_at', sa.DateTime),
    )

    op.create_table('movies', 
        sa.Column('movie_id', sa.Integer, primary_key=True),
        sa.Column('path', sa.String(400), primary_key=True),
        sa.Column('metadata', sa.JSON),
        sa.Column('modified_time', sa.DateTime),
    )

def downgrade():
    raise NotImplemented