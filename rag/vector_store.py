import os
from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.config_handler import pg_conf
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger

from model.factory import openai_embed_model

class VectorStoreService:
    def __init__(
            self,
            chunk_size: int = pg_conf["chunk_size"],
            chunk_overlap: int = pg_conf["chunk_overlap"],
            connection_str: str = f"postgresql+psycopg://{pg_conf['user']}:{pg_conf['password']}@{pg_conf['host']}:{pg_conf['port']}/{pg_conf['dbname']}"
    ):
        self.chukn_size = chunk_size
        self.chunk_overlap = chunk_overlap


        # 构建连接字符串 (Postgres标准连接串)
        self.conn_str = connection_str

        # 初始化 PGVector
        self.vector_store = PGVector(
            embeddings=openai_embed_model,
            collection_name=pg_conf["collection_name_1024"],
            connection=self.conn_str,
            use_jsonb=True,                      # 推荐开启，用于存metadata
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=self.chukn_size,
            chunk_overlap=self.chunk_overlap,
            separators=pg_conf["separators"],
            length_function=len
        )

    def get_retriver(self):
        return self.vector_store.as_retriever(search_kwargs={"k": pg_conf["k"]})

    def load_document(self):
        """
        从数据文件夹内读取数据文件，转为向量存入向量库
        要计算文件的md5做去重
        :return: None
        """
        def get_file_document(file_path: str):
            if file_path.endswith(".pdf"):
                return pdf_loader(file_path)

            if file_path.endswith(".txt"):
                return txt_loader(file_path)

            return []

        allowed_files_paths: list[str] = listdir_with_allowed_type(
            get_abs_path(pg_conf["data_path"]),
            tuple(pg_conf["allow_knowledge_file_type"])
        )

        for path in allowed_files_paths:
            try:
                documents: list[Document] = get_file_document(path)
                if not documents:
                    logger.info(f"[加载知识库] {path}为空")
                    continue

                split_document: list[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"[加载知识库] {path}分片后无有效文本")
                    continue
                # 将内容添加到向量库
                splited_doc = self.vector_store.add_documents(split_document)

                logger.info(f"[加载知识库] {path}内容成功")

                return splited_doc

            except Exception as e:
                logger.error(f"[加载知识库]文件{path}加载失败,错误信息:{str(e)}", exc_info= True)
                continue
        return None
