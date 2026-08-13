from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader


def pdf_loader(file_path: str, password: str | None = None) -> list[Document]:
    return PyPDFLoader(file_path, password).load()

def txt_loader(file_path: str) -> list[Document]:
    return TextLoader(file_path, encoding="utf-8").load()