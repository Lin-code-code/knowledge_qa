import yaml
from utils.path_tool import get_abs_path


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
    """立即加载 YAML 文件并返回普通 dict（兼容旧用法）"""
    abs_path = get_abs_path(relative_path)
    with open(abs_path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


# 懒加载配置单例 —— 首次访问才读磁盘
pg_conf = _LazyConfig("config/pgvector.yml")
rag_conf = _LazyConfig("config/rag.yml")
prompts_conf = _LazyConfig("config/prompts.yml")
db_conf = _LazyConfig("config/database.yml")


if __name__ == '__main__':
    print(pg_conf["collection_name_1024"])
