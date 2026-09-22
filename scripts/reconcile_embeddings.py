"""一次性运维脚本：清理向量库中的孤儿 embedding（幂等，可重复执行）。

背景：上传流程中向量写入（PGVector 独立同步连接）与 uploaded_files 记录
（异步 ORM 事务）分属两个事务，异常时可能产生"有向量、无文件记录"的孤儿数据。
本脚本找出所有 file_id 在 uploaded_files 中不存在的 embedding 并删除。

用法：
  uv run python scripts/reconcile_embeddings.py          # dry-run，仅打印
  uv run python scripts/reconcile_embeddings.py --apply   # 实际删除
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from core.config import env_conf

# 孤儿定义：cmetadata 含 file_id，但 uploaded_files 中不存在该 id（去连字符比较）
ORPHAN_SQL = """
    SELECT COUNT(*)
    FROM langchain_pg_embedding lpe
    WHERE lpe.cmetadata ? 'file_id'
      AND NOT EXISTS (
          SELECT 1 FROM uploaded_files uf
          WHERE REPLACE(uf.id::TEXT, '-', '') = lpe.cmetadata ->> 'file_id'
      );
"""

DELETE_SQL = """
    DELETE FROM langchain_pg_embedding lpe
    WHERE lpe.cmetadata ? 'file_id'
      AND NOT EXISTS (
          SELECT 1 FROM uploaded_files uf
          WHERE REPLACE(uf.id::TEXT, '-', '') = lpe.cmetadata ->> 'file_id'
      );
"""


def main():
    parser = argparse.ArgumentParser(description="清理孤儿向量 embedding")
    parser.add_argument("--apply", action="store_true", help="实际删除（默认仅 dry-run 统计）")
    args = parser.parse_args()

    with psycopg.connect(
        host=env_conf.DB_HOST,
        port=env_conf.DB_PORT,
        user=env_conf.DB_USER,
        password=env_conf.DB_PASSWORD,
        dbname=env_conf.DB_NAME,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(ORPHAN_SQL)
            orphan_count = cur.fetchone()[0]
            print(f"孤儿 embedding 数量: {orphan_count}")

            if args.apply:
                if orphan_count == 0:
                    print("无需清理")
                    return
                cur.execute(DELETE_SQL)
                conn.commit()
                print(f"已删除 {orphan_count} 条孤儿 embedding")
            else:
                print("dry-run：未执行删除（加 --apply 参数执行）")


if __name__ == "__main__":
    main()
