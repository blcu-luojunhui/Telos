from pydantic_settings import BaseSettings, SettingsConfigDict


class MySQLConfig(BaseSettings):
    """数据库配置基类"""

    host: str
    port: int = 3306
    user: str
    password: str
    db: str
    charset: str = "utf8mb4"
    minsize: int = 5
    maxsize: int = 20

    model_config = SettingsConfigDict(
        env_prefix="", case_sensitive=False, extra="ignore"
    )

    def to_dict(self) -> dict:
        """转换为字典格式，用于兼容旧代码"""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "db": self.db,
            "charset": self.charset,
            "minsize": self.minsize,
            "maxsize": self.maxsize,
        }


class BetterMeMySQLConfig(MySQLConfig):
    db_name = "better_me"
    host: str = "localhost"
    user: str = "root"
    password: str = "xxxxxxxx"
    db: str = "better_me"

    model_config = SettingsConfigDict(
        env_prefix="BETTER_ME_DB_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    def async_sqlalchemy_url(self) -> str:
        """SQLAlchemy 异步 DSN（aiomysql 驱动），供 base.py 与 models 使用。"""
        from urllib.parse import quote_plus

        pw = quote_plus(self.password)
        return f"mysql+aiomysql://{self.user}:{pw}@{self.host}:{self.port}/{self.db}?charset={self.charset}"
