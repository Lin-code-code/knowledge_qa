import yaml
from utils.path_tool import get_abs_path

def load_pg_config(config_path: str = get_abs_path("config/pgvector.yml"), encoding: str = "utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_rag_config(config_path: str = get_abs_path("config/rag.yml"), encoding: str = "utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_prompts_config(config_path: str = get_abs_path("config/prompts.yml"), encoding: str = "utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_database_config(config_path: str = get_abs_path("config/database.yml"), encoding: str = "utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)

pg_conf = load_pg_config()
rag_conf = load_rag_config()
prompts_conf = load_prompts_config()
db_conf = load_database_config()


if __name__ == '__main__':
    print(pg_conf["host"])
