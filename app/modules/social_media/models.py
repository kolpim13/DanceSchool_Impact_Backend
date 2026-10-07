from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FacebookPost(Base):
    __tablename__ = "content_facebook_posts"
    page_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    published_at: Mapped[int] = mapped_column(BigInteger, index=True)
    permalink: Mapped[str] = mapped_column(Text)
    preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class FacebookSyncState(Base):
    __tablename__ = "content_facebook_sync_state"
    page_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_attempt_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_success_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FacebookConnection(Base):
    __tablename__ = "content_facebook_connections"
    page_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    page_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    facebook_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connected_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_token_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_token_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_expires_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_data_expires_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_expires_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_data_expires_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    connected_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_checked_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_reacquired_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="disconnected")
    last_error: Mapped[str | None] = mapped_column(String(64), nullable=True)

