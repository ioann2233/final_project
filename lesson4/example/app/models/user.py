from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
import re

if TYPE_CHECKING:
    from models.event import Event

class User(SQLModel, table=True): 
    """
    User model representing application users.
    
    Attributes:
        id (int): Primary key
        email (str): User's email address
        password (str): Hashed password
        created_at (datetime): Account creation timestamp
        events (List[Event]): List of user's events
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(
        ...,  # Required field
        unique=True,
        index=True,
        min_length=5,
        max_length=255
    )
    password: str = Field(..., min_length=4) 
    created_at: datetime = Field(default_factory=datetime.utcnow)
    events: List["Event"] = Relationship(
        back_populates="creator",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "lazy": "selectin"
        }
    )
    
    def __str__(self) -> str:
        return f"Id: {self.id}. Email: {self.email}"

    def validate_email(self) -> bool:
        """
        Validate email format.
        
        Returns:
            bool: True if email is valid
        
        Raises:
            ValueError: If email format is invalid
        """
        pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not pattern.match(self.email):
            raise ValueError("Invalid email format")
        return True
    
    @property
    def event_count(self) -> int:
        """Number of events associated with user"""
        return len(self.events)

    class Config:
        """Model configuration"""
        validate_assignment = True
        arbitrary_types_allowed = True
