import uuid
from datetime import datetime

from pydantic import BaseModel


class File(BaseModel):
    id: int
    name: str
    file: str
    user_id: int
    format: str
    should_delete: bool
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


class Favorite(BaseModel):
    id: int
    user_id: int
    file_id: int

    class Config:
        from_attributes = True


class Files(BaseModel):
    data: File


class FilesFavorite(Files):
    fav: int | None


class FileID(BaseModel):
    file_id: int
