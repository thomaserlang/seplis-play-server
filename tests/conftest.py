import tempfile
from collections.abc import AsyncGenerator

import pytest_asyncio

from seplis_play import config
from seplis_play.database import Database


@pytest_asyncio.fixture(scope='function')
async def play_db_test() -> AsyncGenerator[Database]:
    from seplis_play import scan
    from seplis_play.database import database

    config.test = True
    config.server_id = '123'
    with tempfile.TemporaryDirectory() as dir:
        config.database = f'sqlite:///{dir}/db.sqlite'
        scan.upgrade_scan_db()
        database.setup()
        yield database
        await database.close()
