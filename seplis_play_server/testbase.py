import pytest_asyncio
import tempfile
from seplis_play_server import config
from seplis_play_server.logger import set_logger


def run_file(file_):
    import subprocess
    subprocess.call(['pytest', '--tb=short', str(file_)])


@pytest_asyncio.fixture(scope='function')
async def play_db_test():
    from seplis_play_server.database import database
    from seplis_play_server import scan
    set_logger('play_test')
    config.test = True
    config.server_id = '123'
    with tempfile.TemporaryDirectory() as dir:
        config.database = f'sqlite:///{dir}/db.sqlite'
        scan.upgrade_scan_db()
        database.setup()
        yield database
        await database.close()