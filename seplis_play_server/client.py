from httpx import AsyncClient
from seplis_play_server import config

client = AsyncClient(
    base_url=str(config.api_url),
)