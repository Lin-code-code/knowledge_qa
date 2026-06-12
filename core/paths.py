import os

def get_project_root(marker_file: str = "config") -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))

    while True:
        marker_path = os.path.join(current_dir, marker_file)
        if os.path.exists(marker_path):
            return current_dir

        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError(f"未找到项目根目录标记文件: {marker_file}")

        current_dir = parent_dir


def get_abs_path(relative_path: str) -> str:
    project_root = get_project_root()
    return os.path.join(project_root, relative_path)

if __name__ == '__main__':
    print(get_project_root())
