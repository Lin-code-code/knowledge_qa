import os

def get_project_root(marker_file: str = "config") -> str:
    """
    从当前文件所在目录开始，逐级向上查找 marker_file（默认 config文件夹）。
    找到则返回该目录作为项目根目录。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))

    while True:
        marker_path = os.path.join(current_dir, marker_file)
        if os.path.exists(marker_path):
            return current_dir

        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            # 已到磁盘根目录仍未找到，抛错更安全
            raise FileNotFoundError(f"未找到项目根目录标记文件: {marker_file}")

        current_dir = parent_dir


def get_abs_path(relative_path: str) -> str:
    """
    传递相对路径，获取绝对路径
    :param relative_path: 相对路径
    :return: 绝对路径
    """
    project_root = get_project_root()
    return os.path.join(project_root, relative_path)

if __name__ == '__main__':
    print(get_project_root())