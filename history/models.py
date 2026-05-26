from sqlalchemy import Column, String, Text, BigInteger, DateTime, Index, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass


class Conversation(Base):
    """会话表"""
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(String(64), nullable=False, default="anonymous")
    title = Column(String(256), default="新对话")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_conversations_user", "user_id", "updated_at"),
    )


class Message(Base):
    """消息表"""
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_conv_created", "conversation_id", text("created_at DESC")),
    )


# 创建一个模型类来记录已经上传的文件信息，避免重复上传，包含文件的id、md5字符串、文件名、文件大小、上传时间等字段
class UploadedFile(Base):
    """已上传文件表"""
    __tablename__ = "uploaded_files"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    filename = Column(String(256), nullable=False)
    md5_hex = Column(String(32), nullable=False, unique=True)
    size = Column(BigInteger, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_uploaded_files_md5", "md5_hex"),
    )

