from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from seplis_play import config


class Database:
    def __init__(self) -> None:
        self.engine: AsyncEngine
        self.session: async_sessionmaker[AsyncSession]

    def setup(self) -> None:
        database_url = config.database
        if database_url.startswith('sqlite:'):
            database_url = database_url.replace('sqlite:', 'sqlite+aiosqlite:')

        self.engine = create_async_engine(
            database_url.replace('mysqldb', 'aiomysql').replace('pymysql', 'aiomysql'),
            echo=False,
            pool_recycle=3599,
            pool_pre_ping=True,
        )
        self.session = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def close(self) -> None:
        await self.engine.dispose()


database = Database()
