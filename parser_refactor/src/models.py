from typing import Union, List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
import re


class ObjectType(str, Enum):
    Text = "Text"
    Table = "Table"
    Image = "Image"
    heading = "heading"
    title = "title"
    section_header = "section_header"
    list_item = "list_item"


class PDFObject(BaseModel):
    object_id: str = Field(..., description="Unique identifier for the PDF object")
    type: ObjectType = Field(..., description="Type of the PDF object")
    page: Optional[int] = Field(
        None, description="Page number where the object is located", ge=1
    )
    location: Optional[int] = Field(
        None, description="Vertical position of the object on the page", ge=1
    )
    content: Union[str, List[Dict[str, Any]]] = Field(
        ..., description="Content of the PDF object"
    )

    @validator("object_id")
    def validate_object_id(cls, v):
        if not re.match(r"^[\w\-]+$", v):
            raise ValueError("Invalid object_id format")
        return v

    @validator("content")
    def validate_content(cls, v):
        if isinstance(v, str):
            if not re.search(r"[A-Za-zא-ת]", v):
                raise ValueError("content appears to be gibberish")
        return v


class DocumentModel(BaseModel):
    document: List[PDFObject] = Field(..., description="List of extracted PDF objects")
