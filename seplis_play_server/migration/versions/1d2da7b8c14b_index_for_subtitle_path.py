"""Index for subtitle path

Revision ID: 1d2da7b8c14b
Revises: 962b98bfd654
Create Date: 2023-10-18 09:27:16.446314

"""

# revision identifiers, used by Alembic.
revision = '1d2da7b8c14b'
down_revision = '962b98bfd654'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index(
        'idx_external_subtitle_path',
        'external_subtitles',
        ['path'],
        unique=True,
    )


def downgrade():
    pass
