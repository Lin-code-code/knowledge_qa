from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from utils.path_tool import get_abs_path

class EnvConfig(BaseSettings):
    HOST: str = Field(validation_alias=AliasChoices("HOST", "host"))
    PORT: int = Field(validation_alias=AliasChoices("PORT", "port"))
    USER: str = Field(..., validation_alias=AliasChoices("USER", "user"), repr=False)
    PASSWORD: str = Field(validation_alias=AliasChoices("PASSWORD", "password"))
    DB: str = Field(validation_alias=AliasChoices("DB", "database", "DB_NAME"))

    model_config = SettingsConfigDict(
        env_file=get_abs_path(".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

env_conf = EnvConfig()

if __name__ == '__main__':
    print(env_conf.HOST)
    print(env_conf.PORT)
    print(env_conf.USER)
    print(env_conf.PASSWORD)
    print(env_conf.DB)