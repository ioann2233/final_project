from extensions import db
from models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)

    wallet = db.relationship(
        "Wallet",
        back_populates="owner",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
    transactions = db.relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    tasks = db.relationship(
        "MLTask",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    known_entities = db.relationship(
        "KnownEntity",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def get_balance(self) -> float:
        if not self.wallet:
            return 0.0
        return self.wallet.get_balance()

    def add_balance(self, amount: float) -> None:
        if not self.wallet:
            raise ValueError("У пользователя нет кошелька")
        self.wallet.add_balance(amount)

    def subtract_balance(self, amount: float) -> bool:
        if not self.wallet:
            return False
        return self.wallet.subtract_balance(amount)

    def get_info(self) -> dict:
        info = super().get_info()
        info.update({
            "username": self.username,
            "role": self.role,
            "balance": self.get_balance(),
        })
        return info

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username} role={self.role}>"
