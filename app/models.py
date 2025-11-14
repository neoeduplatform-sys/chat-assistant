"""
Pydantic Models for API Request/Response Validation
====================================================

This module contains all Pydantic models used for:
- Request validation
- Response serialization
- Data validation across the application
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


# ============================================================================
# Chat Models
# ============================================================================

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    question: str = Field(..., min_length=1, max_length=5000, description="User's question")
    course_id: str = Field(..., min_length=1, max_length=255, description="Course identifier")
    user_id: Optional[str] = Field(None, max_length=255, description="Optional user identifier")

    @field_validator('question')
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Question cannot be empty')
        return v.strip()

    @field_validator('course_id')
    @classmethod
    def course_id_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Course ID cannot be empty')
        return v.strip()


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    answer: str = Field(..., description="AI-generated answer")
    sources: Optional[List[str]] = Field(default=None, description="Source documents used")
    course_id: str = Field(..., description="Course identifier")
    user_id: Optional[str] = Field(None, description="User identifier if provided")


# ============================================================================
# Course Configuration Models
# ============================================================================

class CourseConfigBase(BaseModel):
    """Base model for course configuration"""
    course_name: str = Field(..., min_length=1, max_length=500, description="Human-readable course name")
    course_slug: str = Field(..., min_length=1, max_length=255, description="URL-friendly slug")
    table_name: str = Field(..., min_length=1, max_length=255, description="Supabase table name")
    rpc_function: str = Field(..., min_length=1, max_length=255, description="Supabase RPC function name")
    active: bool = Field(default=True, description="Whether the course is active")
    description: Optional[str] = Field(None, description="Course description")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    @field_validator('course_slug')
    @classmethod
    def slug_format(cls, v: str) -> str:
        """Validate slug format (lowercase, hyphens, alphanumeric)"""
        if not v or not v.strip():
            raise ValueError('Course slug cannot be empty')
        slug = v.strip().lower()
        if not all(c.isalnum() or c in '-_' for c in slug):
            raise ValueError('Slug must contain only alphanumeric characters, hyphens, and underscores')
        return slug

    @field_validator('table_name', 'rpc_function')
    @classmethod
    def identifier_format(cls, v: str) -> str:
        """Validate SQL identifier format"""
        if not v or not v.strip():
            raise ValueError('Identifier cannot be empty')
        identifier = v.strip()
        if not all(c.isalnum() or c == '_' for c in identifier):
            raise ValueError('Identifier must contain only alphanumeric characters and underscores')
        return identifier


class CourseConfigCreate(CourseConfigBase):
    """Model for creating a new course configuration"""
    course_id: str = Field(..., min_length=1, max_length=255, description="Unique course identifier")

    @field_validator('course_id')
    @classmethod
    def course_id_format(cls, v: str) -> str:
        """Validate course_id format"""
        if not v or not v.strip():
            raise ValueError('Course ID cannot be empty')
        course_id = v.strip()
        if not all(c.isalnum() or c in '-_' for c in course_id):
            raise ValueError('Course ID must contain only alphanumeric characters, hyphens, and underscores')
        return course_id


class CourseConfigUpdate(BaseModel):
    """Model for updating course configuration (all fields optional)"""
    course_name: Optional[str] = Field(None, min_length=1, max_length=500)
    course_slug: Optional[str] = Field(None, min_length=1, max_length=255)
    table_name: Optional[str] = Field(None, min_length=1, max_length=255)
    rpc_function: Optional[str] = Field(None, min_length=1, max_length=255)
    active: Optional[bool] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('course_slug')
    @classmethod
    def slug_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        slug = v.strip().lower()
        if not all(c.isalnum() or c in '-_' for c in slug):
            raise ValueError('Slug must contain only alphanumeric characters, hyphens, and underscores')
        return slug

    @field_validator('table_name', 'rpc_function')
    @classmethod
    def identifier_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        identifier = v.strip()
        if not all(c.isalnum() or c == '_' for c in identifier):
            raise ValueError('Identifier must contain only alphanumeric characters and underscores')
        return identifier


class CourseConfigResponse(CourseConfigBase):
    """Model for course configuration response"""
    id: int = Field(..., description="Database ID")
    course_id: str = Field(..., description="Unique course identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True  # Allow ORM model conversion


class CourseConfigList(BaseModel):
    """Model for listing course configurations"""
    courses: List[CourseConfigResponse]
    total: int = Field(..., description="Total number of courses")


# ============================================================================
# Ingestion Models
# ============================================================================

class IngestionRequest(BaseModel):
    """Request model for content ingestion endpoint"""
    unique_content_id: str = Field(..., min_length=1, max_length=500, description="Unique content identifier for upserts")
    content: str = Field(..., min_length=1, description="Content text to be indexed")
    course_slug: str = Field(..., min_length=1, max_length=255, description="Course slug (used as course_id)")
    course_name: str = Field(..., description="Course name")
    topic_id: Optional[str] = Field(None, description="Topic identifier")
    model: Optional[str] = Field(None, description="Model identifier")
    version: Optional[str] = Field(None, description="Content version")
    title: Optional[str] = Field(None, description="Content title")
    module: Optional[str] = Field(None, description="Module name")
    notes: Optional[str] = Field(None, description="Additional notes")
    version_data: Optional[str] = Field(None, description="Version date")

    @field_validator('content')
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Content cannot be empty')
        return v


class IngestionResponse(BaseModel):
    """Response model for ingestion endpoint"""
    message: str = Field(..., description="Status message")
    job_id: int = Field(..., description="Ingestion job ID")


# ============================================================================
# Error Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    code: Optional[str] = Field(None, description="Error code")


# ============================================================================
# Health Check Models
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Current timestamp")
    version: Optional[str] = Field(None, description="API version")
