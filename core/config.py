import yaml
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from core.paths import get_abs_path


class EnvConfig(BaseSettings):
    DB_HOST: str = Field(validation_alias=AliasChoices("DB_HOST", "HOST", "host"))
    DB_PORT: int = Field(validation_alias=AliasChoices("DB_PORT", "PORT", "port"))
    DB_USER: str = Field(..., validation_alias=AliasChoices("DB_USER", "USER", "user"), repr=False)
    DB_PASSWORD: str = Field(validation_alias=AliasChoices("DB_PASSWORD", "PASSWORD", "password"))
    DB_NAME: str = Field(validation_alias=AliasChoices("DB_NAME", "DB", "database", "dbname"))

    model_config = SettingsConfigDict(
        env_file=get_abs_path(".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

env_conf = EnvConfig()


class _LazyConfig(dict):
    """懒加载字典：首次访问时才读取 YAML 文件"""
    def __init__(self, relative_path: str):
        self._path = relative_path
        self._loaded = False

    def _ensure(self):
        if not self._loaded:
            self._loaded = True
            abs_path = get_abs_path(self._path)
            with open(abs_path, "r", encoding="utf-8") as f:
                self.update(yaml.load(f, Loader=yaml.FullLoader))

    def __getitem__(self, key):
        self._ensure()
        return super().__getitem__(key)

    def __contains__(self, key):
        self._ensure()
        return super().__contains__(key)

    def get(self, key, default=None):
        self._ensure()
        return super().get(key, default)


def load_yaml_config(relative_path: str) -> dict:
    abs_path = get_abs_path(relative_path)
    with open(abs_path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


pg_conf = _LazyConfig("config/pgvector.yml")
rag_conf = _LazyConfig("config/rag.yml")
prompts_conf = _LazyConfig("config/prompts.yml")
db_conf = _LazyConfig("config/database.yml")


if __name__ == '__main__':
    print(pg_conf["collection_name_1024"])
    print(env_conf.DB_HOST)
