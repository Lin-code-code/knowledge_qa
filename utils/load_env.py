from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from utils.path_tool import get_abs_path

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

if __name__ == '__main__':
    print(env_conf.DB_HOST)
    print(env_conf.DB_PORT)
    print(env_conf.DB_USER)
    print(env_conf.DB_PASSWORD)
    print(env_conf.DB_NAME)
    import os
    print(f"SILICONFLOW_API_KEY={'已配置' if os.environ.get('SILICONFLOW_API_KEY') else '未配置'}")