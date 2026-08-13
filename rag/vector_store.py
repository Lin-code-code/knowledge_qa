from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import pg_conf, env_conf
from core.logger import logger
from utils.file_handler import pdf_loader, txt_loader

from rag.model.factory import get_embed_model

class VectorStoreService:
    def __init__(
            self,
            chunk_size: int = pg_conf["chunk_size"],
            chunk_overlap: int = pg_conf["chunk_overlap"],
            connection_str: str | None = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        if connection_str is None:
            connection_str = (
                f"postgresql+psycopg://{env_conf.DB_USER}:{env_conf.DB_PASSWORD}"
                f"@{env_conf.DB_HOST}:{env_conf.DB_PORT}/{env_conf.DB_NAME}"
            )
        self.conn_str = connection_str

        self.vector_store = PGVector(
            embeddings=get_embed_model(),
            collection_name=pg_conf["collection_name_1024"],
            connection=self.conn_str,
            use_jsonb=True,
        )

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=pg_conf["separators"],
            length_function=len
        )

    def search_with_scores(self, query: str, k: int) -> list[tuple[Document, float]]:
        """
        带距离分数的向量检索。
        PGVector 返回 (Document, distance)，distance 为余弦距离 ∈ [0,2]，越小越相似。
        """
        return self.vector_store.similarity_search_with_score(query, k=k)

    def delete_documents(self, ids: list[str]) -> None:
        """按 chunk id 删除向量（用于上传失败时的补偿删除）。"""
        if not ids:
            return
        self.vector_store.delete(ids=ids)

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

            split_document: list[Document] = self.splitter.split_documents(documents)

            if not split_document:
                logger.warning(f"[加载知识库] {target_path}分片后无有效文本")
                return None

            # 为每个chunk添加file_id元数据
            for doc in split_document:
                doc.metadata["file_id"] = file_id

            # 自定义分块id
            chunk_ids = [f"{file_id}-chunk{i}" for i in range(len(split_document))]

            # 将内容添加到向量库
            added_ids = self.vector_store.add_documents(split_document, ids=chunk_ids)

            logger.info(f"[加载知识库] {target_path}内容成功, 写入{len(added_ids)}个chunk")

            return added_ids

        except Exception as e:
            logger.error(f"[加载知识库]文件{target_path}加载失败,错误信息:{str(e)}", exc_info=True)
        return None
