from sqlalchemy import BigInteger, Column, DateTime, Float, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(String(64), nullable=False)
    memory_type = Column(String(32), nullable=False, default="preference")
    memory_key = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    source_message_id = Column(BigInteger, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_memory_user_active", "user_id", "status", "expires_at"),
        Index("uq_memory_user_key", "user_id", "memory_key", unique=True),
    )
