from elasticsearch import AsyncElasticsearch

es_client = None


def init_es(app):
    global es_client
    es_client = AsyncElasticsearch(hosts=app.config["ES_HOSTS"])


async def close_es():
    if es_client:
        await es_client.close()
