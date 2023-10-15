"""External subtitles

Revision ID: 962b98bfd654
Revises: 9fbe5febc089
Create Date: 2023-10-15 16:53:07.158296

"""

# revision identifiers, used by Alembic.
revision = '962b98bfd654'
down_revision = '9fbe5febc089'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('external_subtitles',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('path', sa.String(1000), nullable=False),
        sa.Column('type', sa.String(100), nullable=False),
        sa.Column('language', sa.String(100), nullable=False),
        sa.Column('forced', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('sdh', sa.Boolean(), nullable=False, server_default='0'),
    )


def downgrade():
    pass
