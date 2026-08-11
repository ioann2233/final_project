from extensions import db
from models.base import BaseModel


class MLModel(BaseModel):
    __tablename__ = "ml_models"

    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price = db.Column(db.Float, nullable=False, default=0.0)
    model_path = db.Column(db.String(255), nullable=False, default="yolov8n.pt")
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    tasks = db.relationship("MLTask", back_populates="model", lazy="select")

    def predict(self, image_path: str) -> list:
        from worker.predictor import run_prediction

        return run_prediction(self.name, self.model_path, image_path)

    def get_info(self) -> dict:
        info = super().get_info()
        info.update({
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "model_path": self.model_path,
            "is_active": self.is_active,
        })
        return info

    def __repr__(self) -> str:
        return f"<MLModel id={self.id} name={self.name} price={self.price}>"
