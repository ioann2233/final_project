import json
from typing import List, Optional

from extensions import db
from models.base import BaseModel


class KnownEntity(BaseModel):
    __tablename__ = "known_entities"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    entity_type = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)
    descriptor = db.Column(db.Text, nullable=False)

    owner = db.relationship("User", back_populates="known_entities")

    def get_descriptor(self) -> List[float]:
        return json.loads(self.descriptor)

    def get_info(self) -> dict:
        info = super().get_info()
        info.update(
            {
                "user_id": self.user_id,
                "entity_type": self.entity_type,
                "name": self.name,
                "image_path": self.image_path,
            }
        )
        return info

    @staticmethod
    def serialize_descriptor(values: List[float]) -> str:
        return json.dumps(values)

    def __repr__(self) -> str:
        return f"<KnownEntity id={self.id} type={self.entity_type} name={self.name}>"
