from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User

class EventBase(SQLModel):
    """
    Base Event model with common fields.
    
    Attributes:
        title (str): Event title
        image (str): URL or path to event image
        description (str): Event description
        location (Optional[str]): Event location
        tags (Optional[List[str]]): Event tags
    """
    title: str = Field(..., min_length=1, max_length=100)
    image: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1, max_length=1000)

class Event(EventBase, table=True):
    """
    Event model representing events in the system.
    
    Attributes:
        id (Optional[int]): Primary key
        creator_id (Optional[int]): Foreign key to User
        creator (Optional[User]): Relationship to User
        created_at (datetime): Event creation timestamp
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    creator_id: Optional[int] = Field(default=None, foreign_key="user.id")
    creator: Optional["User"] = Relationship(
        back_populates="events",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def __str__(self) -> str:
        result = (f"Id: {self.id}. Title: {self.title}. Creator: {self.creator.email}")
        return result
    
    @property
    def short_description(self) -> str:
        """Returns truncated description for preview"""
        max_length = 100
        return (f"{self.description[:max_length]}..."
                if len(self.description) > max_length
                else self.description)

class EventCreate(EventBase):
    """Schema for creating new events"""
    pass

class EventUpdate(EventBase):
    """Schema for updating existing events"""
    title: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None

    class Config:
        """Model configuration"""
        validate_assignment = True