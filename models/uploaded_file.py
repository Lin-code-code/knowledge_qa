from sqlalchemy import Column, String, BigInteger, DateTime, Index, func
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    filename = Column(String(256), nullable=False)
    md5_hex = Column(String(32), nullable=False, unique=True)
    size = Column(BigInteger, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_uploaded_files_md5", "md5_hex"),
    )
