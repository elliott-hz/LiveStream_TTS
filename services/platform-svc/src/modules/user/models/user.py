"""User domain model.

The central entity for the user-svc.  Each user has a role (RBAC) and
belongs to zero or more stores via the ``UserStoreLink`` association.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, relationship

from libs.db import Base


class UserStoreLink(Base):
    """Many-to-many association between users and stores."""

    __tablename__ = "user_store_links"

    user_id: Mapped[str] = Column(
        String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[str] = Column(
        String(36), ForeignKey("stores.store_id", ondelete="CASCADE"), primary_key=True
    )


class User(Base):
    """Platform user / merchant account.

    Maps directly to the proto ``User`` message.
    """

    __tablename__ = "users"

    user_id: Mapped[str] = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = Column(
        String(100), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = Column(
        String(255), unique=True, nullable=False, index=True
    )
    phone: Mapped[str | None] = Column(String(20), nullable=True)
    password_hash: Mapped[str] = Column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = Column(String(500), nullable=True)
    role_id: Mapped[str | None] = Column(
        String(36), ForeignKey("roles.role_id"), nullable=True, index=True
    )
    current_store_id: Mapped[str | None] = Column(
        String(36), ForeignKey("stores.store_id"), nullable=True
    )
    status: Mapped[str] = Column(
        String(20), nullable=False, default="active", index=True
    )
    created_at: Mapped[datetime] = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    role = relationship("Role", back_populates="users", lazy="joined")
    stores = relationship(
        "Store", secondary="user_store_links", back_populates="users", lazy="selectin"
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_suspended(self) -> bool:
        return self.status == "suspended"

    @property
    def is_deleted(self) -> bool:
        return self.status == "deleted"

    def __repr__(self) -> str:
        return f"<User {self.username} (id={self.user_id})>"
