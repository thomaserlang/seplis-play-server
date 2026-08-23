"""Compress media metadata and separate embedded subtitle cache

Revision ID: a13e0d4c9f72
Revises: 38b684d84d2e
Create Date: 2026-08-23 00:00:00.000000

"""

from compression import zstd

import orjson
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a13e0d4c9f72'
down_revision = '38b684d84d2e'


def blob_type() -> sa.LargeBinary:
    return (
        sa.LargeBinary()
        .with_variant(mysql.MEDIUMBLOB(), 'mysql')
        .with_variant(mysql.MEDIUMBLOB(), 'mariadb')
    )


def compress_metadata(table_name: str) -> None:
    op.add_column(table_name, sa.Column('metadata_zstd', blob_type(), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(f'SELECT path, metadata FROM {table_name} WHERE metadata IS NOT NULL')
    ).mappings()
    for row in rows:
        metadata = row['metadata']
        if isinstance(metadata, str | bytes | bytearray | memoryview):
            metadata = orjson.loads(metadata)
        compressed = zstd.compress(orjson.dumps(metadata))
        connection.execute(
            sa.text(
                f'UPDATE {table_name} SET metadata_zstd = :metadata WHERE path = :path'
            ),
            {'metadata': compressed, 'path': row['path']},
        )
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column('metadata')
        batch_op.alter_column(
            'metadata_zstd', existing_type=blob_type(), new_column_name='metadata'
        )


def decompress_metadata(table_name: str) -> None:
    op.add_column(table_name, sa.Column('metadata_json', sa.JSON(), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(f'SELECT path, metadata FROM {table_name} WHERE metadata IS NOT NULL')
    ).mappings()
    for row in rows:
        metadata = zstd.decompress(bytes(row['metadata'])).decode()
        connection.execute(
            sa.text(
                f'UPDATE {table_name} SET metadata_json = :metadata WHERE path = :path'
            ),
            {'metadata': metadata, 'path': row['path']},
        )
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column('metadata')
        batch_op.alter_column(
            'metadata_json', existing_type=sa.JSON(), new_column_name='metadata'
        )


def upgrade() -> None:
    op.create_table(
        'cached_subtitles',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('source_path', sa.String(400), nullable=False),
        sa.Column('stream_index', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('language', sa.String(100), nullable=False),
        sa.Column('forced', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('content', blob_type(), nullable=True),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text('DELETE FROM external_subtitles WHERE source_path IS NOT NULL')
    )
    with op.batch_alter_table('external_subtitles') as batch_op:
        batch_op.drop_index('uq_cached_subtitle_source_stream_type')
        batch_op.drop_column('stream_index')
        batch_op.drop_column('source_path')

    op.create_index(
        'uq_cached_subtitle_source_stream_type',
        'cached_subtitles',
        ['source_path', 'stream_index', 'type'],
        unique=True,
    )

    compress_metadata('episodes')
    compress_metadata('movies')


def downgrade() -> None:
    decompress_metadata('movies')
    decompress_metadata('episodes')

    op.drop_table('cached_subtitles')
    with op.batch_alter_table('external_subtitles') as batch_op:
        batch_op.add_column(sa.Column('source_path', sa.String(400)))
        batch_op.add_column(sa.Column('stream_index', sa.Integer()))
        batch_op.create_index(
            'uq_cached_subtitle_source_stream_type',
            ['source_path', 'stream_index', 'type'],
            unique=True,
        )
