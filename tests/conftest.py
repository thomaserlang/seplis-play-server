import pytest_asyncio
import tempfile
from seplis_play_server import config
from seplis_play_server.logger import set_logger


@pytest_asyncio.fixture(scope="function")
async def play_db_test():
    from seplis_play_server.database import database
    from seplis_play_server import scan

    set_logger("play_test")
    config.test = True
    config.server_id = "123"
    with tempfile.TemporaryDirectory() as dir:
        import logging
        logging.error(f"Using temp dir: {dir}")
        config.database = f"sqlite:///{dir}/db.sqlite"
        scan.upgrade_scan_db()
        logging.error(f"Using database: {config.database}")
        database.setup()
        logging.error("Database setup")
        yield database
        logging.error("Closing database")
        await database.close()
