import os

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from seplis_play import config
from seplis_play.database import Database
from seplis_play.utils.sa_zstd_json_utils import ZstdJson
from seplis_play.utils.sa_zstd_text_utils import ZstdText


@pytest.mark.asyncio
@pytest.mark.parametrize('driver', ['pymysql', 'mysqldb', 'aiomysql', 'asyncmy'])
async def test_mysql_driver_selection(
    monkeypatch: pytest.MonkeyPatch, driver: str
) -> None:
    url = f'mysql+{driver}://user:pymysql@localhost/aiomysql?charset=utf8mb4'
    monkeypatch.setattr(config, 'database', url)
    database = Database()
    database.setup()
    try:
        assert database.engine.dialect.driver == 'asyncmy'
        assert database.engine.url == make_url(url).set(drivername='mysql+asyncmy')
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_mysql_binary_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get('SEPLIS_TEST_MYSQL_URL')
    if not url:
        pytest.skip('Set SEPLIS_TEST_MYSQL_URL to run the MySQL integration test')
    monkeypatch.setattr(config, 'database', url)
    database = Database()
    database.setup()
    table = sa.Table(
        'test_binary_round_trip',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('payload', sa.LargeBinary),
        sa.Column('metadata', ZstdJson),
        sa.Column('subtitle', ZstdText),
        prefixes=['TEMPORARY'],
    )
    metadata = {'title': 'Tokyo Revengers', 'streams': [{'language': '日本語'}]}
    subtitle = 'Dialogue: 日本語, quotes \' and ", backslash \\ and newline\n'
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(table.create)
            for i, payload in enumerate([b'', bytes(range(256))], start=1):
                await connection.execute(
                    table.insert().values(
                        id=i, payload=payload, metadata=metadata, subtitle=subtitle
                    )
                )
                row = (
                    await connection.execute(sa.select(table).where(table.c.id == i))
                ).one()
                assert row.payload == payload
                assert row.metadata == metadata
                assert row.subtitle == subtitle
    finally:
        await database.close()
