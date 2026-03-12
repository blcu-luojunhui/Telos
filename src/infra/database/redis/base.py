import redis.asyncio as redis

redis_client = None


def init_redis(app):
    global redis_client
    redis_client = redis.from_url(app.config["REDIS_URL"], decode_responses=True)


async def close_redis():
    if redis_client:
        await redis_client.close()
