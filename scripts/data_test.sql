-- 查询每个上传文件的名称、大小和对应的chunk数量，并按chunk数量降序排序
SELECT
    uf.filename,
    uf.size,
    COUNT(lpe.id) AS chunk_count
FROM uploaded_files uf
JOIN langchain_pg_embedding lpe
    ON REPLACE(uf.id::TEXT, '-', '') = (lpe.cmetadata ->> 'file_id')
GROUP BY uf.id, uf.filename, uf.size
ORDER BY chunk_count DESC;


-- 利用索引的写法（等价，但可能被优化器更好利用）
SELECT
    uf.filename,
    uf.size,
    COUNT(*) AS chunk_count
FROM uploaded_files uf
JOIN langchain_pg_embedding lpe
    ON (REPLACE(uf.id::TEXT, '-', '')) = (lpe.cmetadata ->> 'file_id')
WHERE lpe.cmetadata ? 'file_id'  -- 提前过滤无效行
GROUP BY uf.id, uf.filename, uf.size
ORDER BY chunk_count DESC;

-- 清空表数据
BEGIN;
TRUNCATE TABLE langchain_pg_embedding, langchain_pg_collection, uploaded_files  RESTART IDENTITY CASCADE;
-- 确认无误后提交
COMMIT;
-- ROLLBACK;  -- 如果发现问题，改为回滚