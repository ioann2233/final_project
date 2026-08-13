from auth.hash_password import HashPassword
from service.testing.user import get_user_by_username

hash_password = HashPassword()


def authenticate_user(username: str, password: str):
    user = get_user_by_username(username.strip())
    if not user:
        return None

    stored = user.password or ""
    if stored.startswith("$2"):
        try:
            if hash_password.verify_hash(password, stored):
                return user
        except ValueError:
            return None
        return None

    if stored == password:
        return user
    return None
