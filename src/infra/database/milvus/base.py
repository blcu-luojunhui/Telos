from pymilvus import connections, utility


def init_milvus(app):
    connections.connect(
        alias="default", host=app.config["MILVUS_HOST"], port=app.config["MILVUS_PORT"]
    )


def close_milvus():
    connections.disconnect("default")
