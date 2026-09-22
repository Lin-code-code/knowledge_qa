"""一次性运维脚本：为 langchain_pg_embedding 创建 HNSW 向量索引（幂等，可重复执行）。

背景：langchain_pg_embedding.embedding 列可能为无维度 vector（PG 15+ 允许），
HNSW/ivfflat 索引要求固定维度。脚本会自动检测并执行：
  1. 检查列类型与数据维度
  2. 若为无维度 vector 且数据均为 1024 维 → ALTER 为 vector(1024)
  3. 创建 HNSW 索引

用法：uv run python scripts/create_hnsw_index.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from core.config import env_conf


def main():
    with psycopg.connect(
        host=env_conf.DB_HOST,
        port=env_conf.DB_PORT,
        user=env_conf.DB_USER,
        password=env_conf.DB_PASSWORD,
        dbname=env_conf.DB_NAME,
    ) as conn:
        with conn.cursor() as cur:
            # 1) 现有索引
            cur.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'langchain_pg_embedding'"
            )
            print("现有索引:", [r[0] for r in cur.fetchall()])

            # 2) 列类型
            cur.execute(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid = 'langchain_pg_embedding'::regclass AND attname = 'embedding'"
            )
            col_type = cur.fetchone()[0]
            print("embedding 列类型:", col_type)

            # 3) 数据行数与维度分布
            cur.execute("SELECT COUNT(*) FROM langchain_pg_embedding")
            row_count = cur.fetchone()[0]
            print("数据行数:", row_count)
            if row_count > 0:
                cur.execute(
                    "SELECT vector_dims(embedding), COUNT(*) "
                    "FROM langchain_pg_embedding GROUP BY 1"
                )
                print("维度分布:", cur.fetchall())

            # 4) 无维度 vector → 升级为 vector(1024)
            if col_type == "vector":
                cur.execute(
                    "SELECT DISTINCT vector_dims(embedding) FROM langchain_pg_embedding"
                )
                dims = [r[0] for r in cur.fetchall()]
                if dims and dims != [1024]:
                    print("数据维度不为 1024，跳过 ALTER，HNSW 索引无法创建")
                    return
                cur.execute(
                    "ALTER TABLE langchain_pg_embedding "
                    "ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector(1024)"
                )
                conn.commit()
                print("列已升级为 vector(1024)")
            elif col_type != "vector(1024)":
                print(f"列类型 {col_type} 与预期不符，跳过索引创建")
                return

            # 5) 创建 HNSW 索引
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_embedding_hnsw "
                "ON langchain_pg_embedding USING hnsw (embedding vector_cosine_ops)"
            )
            conn.commit()
            print("HNSW 索引创建完成")

            cur.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'langchain_pg_embedding'"
            )
            print("创建后索引:", [r[0] for r in cur.fetchall()])


if __name__ == "__main__":
    main()
