from __future__ import annotations

import json

import redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("cache")


class RedisCache:
    def __init__(self):
        self._client: redis.Redis | None = None
        self._available = False

        try:
            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            self._client = client
            self._available = True
            logger.info("redis_connected")
        except RedisError as exc:
            logger.warning("redis_unavailable_fallback", error=str(exc))

    @property
    def available(self) -> bool:
        return self._available

    def get_json(self, key: str) -> dict | None:
        if not self._client:
            return None
        try:
            value = self._client.get(key)
            if not value:
                return None
            return json.loads(value)
        except (RedisError, json.JSONDecodeError) as exc:
            logger.warning("redis_get_failed", key=key, error=str(exc))
            return None

    def set_json(self, key: str, value: dict, ttl_seconds: int) -> None:
        if not self._client:
            return
        try:
            self._client.setex(key, ttl_seconds, json.dumps(value))
        except (RedisError, TypeError) as exc:
            logger.warning("redis_set_failed", key=key, error=str(exc))
