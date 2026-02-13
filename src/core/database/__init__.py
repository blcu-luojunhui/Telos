from .mysql import init_mysql, close_mysql
# from .redis import init_redis, close_redis
# from .es import init_es, close_es
# from .milvus import init_milvus, close_milvus


def init_db(app):
    init_mysql(app)
    # init_redis(app)
    # init_es(app)
    # init_milvus(app)


async def close_db():
    await close_mysql()
    # await close_redis()
    # await close_es()
    # close_milvus()
