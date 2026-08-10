from models.user import User
from models.event import Event
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from typing import List, Optional

def get_all_users(session: Session) -> List[User]:
    """
    Retrieve all users with their events.
    
    Args:
        session: Database session
    
    Returns:
        List[User]: List of all users
    """
    try:
        statement = select(User).options(
            selectinload(User.events).selectinload(Event.creator)
        )
        users = session.exec(statement).all()
        return users
    except Exception as e:
        raise

def get_user_by_id(user_id: int, session: Session) -> Optional[User]:
    """
    Get user by ID.
    
    Args:
        user_id: User ID to find
        session: Database session
    
    Returns:
        Optional[User]: Found user or None
    """
    try:
        statement = select(User).where(User.id == user_id).options(
            selectinload(User.events)
        )
        user = session.exec(statement).first()
        return user
    except Exception as e:
        raise

def get_user_by_email(email: str, session: Session) -> Optional[User]:
    """
    Get user by email.
    
    Args:
        email: Email to search for
        session: Database session
    
    Returns:
        Optional[User]: Found user or None
    """
    try:
        statement = select(User).where(User.email == email).options(
            selectinload(User.events)
        )
        user = session.exec(statement).first()
        return user
    except Exception as e:
        raise

def create_user(user: User, session: Session) -> User:
    """
    Create new user.
    
    Args:
        user: User to create
        session: Database session
    
    Returns:
        User: Created user with ID
    """
    try:
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    except Exception as e:
        session.rollback()
        raise

def delete_user(user_id: int, session: Session) -> bool:
    """
    Delete user by ID.
    
    Args:
        user_id: User ID to delete
        session: Database session
    
    Returns:
        bool: True if deleted, False if not found
    """
    try:
        user = get_user_by_id(user_id, session)
        if user:
            session.delete(user)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise