from typing import List, Optional


class LoginForm:
    def __init__(self, username: Optional[str], password: Optional[str]):
        self.errors: List[str] = []
        self.username = (username or "").strip()
        self.password = password or ""

    def is_valid(self) -> bool:
        if not self.username:
            self.errors.append("Логин обязателен")
        if not self.password:
            self.errors.append("Пароль обязателен")
        return not self.errors


class RegisterForm:
    def __init__(
        self,
        username: Optional[str],
        password: Optional[str],
        initial_balance: float = 0.0,
    ):
        self.errors: List[str] = []
        self.username = (username or "").strip()
        self.password = password or ""
        self.initial_balance = initial_balance

    def is_valid(self) -> bool:
        if not self.username:
            self.errors.append("Логин обязателен")
        elif len(self.username) < 3:
            self.errors.append("Логин должен быть не короче 3 символов")
        if not self.password or len(self.password) < 4:
            self.errors.append("Пароль должен быть не короче 4 символов")
        if self.initial_balance < 0:
            self.errors.append("Начальный баланс должен быть ≥ 0")
        return not self.errors
