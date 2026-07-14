"""Store domain model.

Represents a merchant store that can be linked to one or more users.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, relationship

from libs.db import Base


class Store(Base):
    """Merchant store entity.

    Each store belongs to one or more users (many-to-many via
    ``UserStoreLink``).  The ``platforms`` column stores a JSON dict
    matching the proto ``StorePlatform`` message, e.g.::

        {"taobao": true, "douyin": true, "jd": false, ...}
    """

    __tablename__ = "stores"

    store_id: Mapped[str] = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = Column(String(200), nullable=False)
    logo_url: Mapped[str | None] = Column(String(500), nullable=True)
    platforms: Mapped[dict] = Column(JSON, nullable=False, default=dict)
    status: Mapped[str] = Column(
        String(20), nullable=False, default="active", index=True
    )
    created_at: Mapped[datetime] = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    users = relationship("User", secondary="user_store_links", back_populates="stores")

    def __repr__(self) -> str:
        return f"<Store {self.name} (id={self.store_id})>"
