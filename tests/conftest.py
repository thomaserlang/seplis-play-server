import tempfile

import pytest_asyncio

from seplis_play_server import config
from seplis_play_server.logger import set_logger


@pytest_asyncio.fixture(scope="function")
async def play_db_test():
    from seplis_play_server import scan
    from seplis_play_server.database import database

    set_logger("play_test")
    config.test = True
    config.server_id = "123"
    with tempfile.TemporaryDirectory() as dir:
        config.database = f"sqlite:///{dir}/db.sqlite"
        scan.upgrade_scan_db()
        database.setup()
        yield database
        await database.close()
