"""Role and permission domain model.

Defines the ``Role`` entity with a JSON-based permission list for RBAC.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, relationship

from libs.db import Base


class Role(Base):
    """RBAC role entity.

    Each role has a unique name and a list of permission strings (e.g.
    ``"product:write"``, ``"user:read"``).

    Well-known role names (see proto ``Role.name``):
        * super_admin
        * platform_operator
        * content_reviewer
        * merchant_admin
        * merchant_editor
        * merchant_viewer
    """

    __tablename__ = "roles"

    role_id: Mapped[str] = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = Column(String(50), unique=True, nullable=False, index=True)
    permissions: Mapped[list] = Column(JSON, nullable=False, default=list)
    description: Mapped[str | None] = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    users = relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.name} (id={self.role_id})>"
