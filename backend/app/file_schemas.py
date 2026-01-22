from typing import List

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    id: str
    name: str
    size: str
    type: str
    url: str
    filename: str


class FileListResponse(BaseModel):
    user_id: str
    files: List[FileMetadata] = Field(default_factory=list)


class FileUploadResponse(FileListResponse):
    pass
