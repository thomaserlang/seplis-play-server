"""Add cached subtitle assets

Revision ID: 38b684d84d2e
Revises: 1d2da7b8c14b
Create Date: 2026-08-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '38b684d84d2e'
down_revision = '1d2da7b8c14b'


def upgrade() -> None:
    op.add_column('external_subtitles', sa.Column('source_path', sa.String(400)))
    op.add_column('external_subtitles', sa.Column('stream_index', sa.Integer()))
    op.create_index(
        'uq_cached_subtitle_source_stream_type',
        'external_subtitles',
        ['source_path', 'stream_index', 'type'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        'uq_cached_subtitle_source_stream_type', table_name='external_subtitles'
    )
    op.drop_column('external_subtitles', 'stream_index')
    op.drop_column('external_subtitles', 'source_path')
