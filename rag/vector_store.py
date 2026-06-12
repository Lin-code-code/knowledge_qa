from pathlib import Path
from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.config_handler import pg_conf
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type
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

    def load_document(self, file_id: str, target_path: str):
        """
            加载当个文件
        :return: None
        """
        def get_file_document(file_path: str):
            if file_path.endswith(".pdf"):
                return pdf_loader(file_path)

            if file_path.endswith(".txt"):
                return txt_loader(file_path)

            return []

        if target_path is None:
            logger.warning(f"[加载知识库] 未找到 file_id={file_id} 对应的文件")
            return None

        try:
            documents: list[Document] = get_file_document(target_path)
            if not documents:
                logger.info(f"[加载知识库] {target_path}为空")
                return None

            split_document: list[Document] = self.spliter.split_documents(documents)

            if not split_document:
                logger.warning(f"[加载知识库] {target_path}分片后无有效文本")
                return None

            # 为每个chunk添加file_id元数据
            for doc in split_document:
                doc.metadata["file_id"] = file_id

            # 自定义分块id
            chunk_ids = [f"{file_id}-chunk{i}" for i in range(len(split_document))]

            # 将内容添加到向量库
            splited_document = self.vector_store.add_documents(split_document, ids=chunk_ids)

            logger.info(f"[加载知识库] {target_path}内容成功")

            return splited_document

        except Exception as e:
            logger.error(f"[加载知识库]文件{target_path}加载失败,错误信息:{str(e)}", exc_info=True)
        return None
