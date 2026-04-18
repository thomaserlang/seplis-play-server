from httpx import AsyncClient

from seplis_play.config import config

client = AsyncClient(
    base_url=str(config.api_url),
)
