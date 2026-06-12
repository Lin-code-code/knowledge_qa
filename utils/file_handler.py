import os, hashlib
from typing import Optional
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader

def get_file_md5_hex(file_path: str) -> Optional[str]:
    if not os.path.exists(file_path):
        print(f"[md5计算]文件{file_path}不存在")
        return None

    if not os.path.isfile(file_path):
        print(f"[md5计算]路径{file_path}不是文件")
        return None

    md5_obj = hashlib.md5()

    chunk_size = 4096
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)

            md5_hex = md5_obj.hexdigest()
            return md5_hex
    except Exception as e:
        print(f"[md5计算]文件{file_path}计算md5失败,错误信息:{str(e)}")
        return None

def listdir_with_allowed_type(path: str, allowed_type: tuple[str, ...]) -> tuple[str, ...]:
    if not os.path.isdir(path):
        print(f"[文件列表]路径{path}不是目录")
        return ()

    files: list[str] = []
    for f in os.listdir(path):
        if f.endswith(allowed_type):
            files.append(os.path.join(path, f))
    return tuple(files)


def pdf_loader(file_path: str, password: str | None = None) -> list[Document]:
    return PyPDFLoader(file_path, password).load()

def txt_loader(file_path: str) -> list[Document]:
    return TextLoader(file_path, encoding="utf-8").load()