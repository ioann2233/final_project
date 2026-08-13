from typing import List, Optional

from auth.hash_password import HashPassword
from extensions import db
from models.user import User
from models.wallet import Wallet

hash_password = HashPassword()


def create_user(
    username: str,
    password: str,
    role: str = "user",
    initial_balance: float = 0.0,
) -> User:
    existing = get_user_by_username(username)
    if existing:
        raise ValueError(f"Пользователь '{username}' уже существует")

    user = User(
        username=username,
        password=hash_password.create_hash(password),
        role=role,
    )
    db.session.add(user)
    db.session.flush()

    wallet = Wallet(owner_id=user.id, balance=initial_balance)
    db.session.add(wallet)
    db.session.commit()
    db.session.refresh(user)
    return user


def get_user_by_id(user_id: int) -> Optional[User]:
    return db.session.get(User, user_id)


def get_user_by_username(username: str) -> Optional[User]:
    return db.session.query(User).filter_by(username=username).first()


def get_all_users() -> List[User]:
    return db.session.query(User).order_by(User.id).all()
