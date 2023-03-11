from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from seplis_play_server import config, utils
import os.path
import alembic.config
from alembic import command

def get_config():
    cfg = alembic.config.Config(
        os.path.dirname(
            os.path.abspath(__file__)
        )+'/alembic.ini'
    )
    cfg.set_main_option('script_location', 'seplis_play_server:migration')
    cfg.set_main_option('url', config.database)
    return cfg

def upgrade():
    cfg = get_config()
    command.upgrade(cfg, 'head')


class Database:

    def __init__(self):
        self.engine = None
        self.session = None

    def setup(self):
        self.engine = create_async_engine(
            config.database.replace('mysqldb', 'aiomysql').replace('pymysql', 'aiomysql').replace('sqlite:', 'sqlite+aiosqlite:'),
            echo=False,
            pool_recycle=3599,
            pool_pre_ping=True,
            json_serializer=lambda obj: utils.json_dumps(obj),
            json_deserializer=lambda s: utils.json_loads(s),
        )
        self.session = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def close(self):
        await self.engine.dispose()

database = Database()