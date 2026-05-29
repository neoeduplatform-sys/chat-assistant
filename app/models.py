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
    """Request model for chat endpoint.

    ``course_id`` y ``user_id`` son opcionales: el backend los obtiene del JWT
    validado y, por seguridad, prioriza los valores del token por encima de los
    enviados en el cuerpo del request.
    """
    question: str = Field(..., min_length=1, max_length=5000, description="User's question")
    course_id: Optional[str] = Field(
        None,
        max_length=255,
        description="Course identifier (se ignora si el token lo provee)",
    )
    user_id: Optional[str] = Field(None, max_length=255, description="Optional user identifier")

    @field_validator('question')
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Question cannot be empty')
        return v.strip()

    @field_validator('course_id')
    @classmethod
    def course_id_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.strip():
            raise ValueError('Course ID cannot be empty')
        return v.strip()


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    answer: str = Field(..., description="AI-generated answer")
    sources: Optional[List[str]] = Field(default=None, description="Source documents used")
    course_id: str = Field(..., description="Course identifier")
    user_id: Optional[str] = Field(None, description="User identifier if provided")


class ChatHistoryMessageItem(BaseModel):
    """Single persisted chat message for history API."""
    id: int = Field(..., description="Database message id")
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message body")
    created_at: datetime = Field(..., description="UTC timestamp")


class ChatHistoryResponse(BaseModel):
    """Paginated conversation history for a user within a course."""
    conversation_id: Optional[str] = Field(
        None,
        description="UUID of chat_conversations row; null if no thread exists yet",
    )
    course_id: str = Field(..., description="Course identifier")
    user_id: str = Field(..., description="User identifier")
    messages: List[ChatHistoryMessageItem] = Field(default_factory=list)
    summary: Optional[str] = Field(
        None,
        description="Rolling summary (layer B), if any",
    )
    total_count: int = Field(0, description="Total messages in this conversation")
    limit: int = Field(..., description="Page size used for this response")
    offset: int = Field(
        ...,
        description="Pagination offset (from end when tail=true on /api/chat/history)",
    )
    has_more: bool = Field(
        False,
        description="True if older messages exist beyond this page (tail=true: before this window)",
    )


class ChatScopeMessageItem(BaseModel):
    """Message as it would be merged into the LLM synthesis prompt (no id/timestamp)."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message body, exactly as it would be merged")


class ChatScopeResponse(BaseModel):
    """Preview of Layer A + Layer B that /api/chat would merge with the next question."""
    conversation_id: Optional[str] = Field(
        None,
        description="UUID of chat_conversations row; null if no thread exists yet",
    )
    course_id: str = Field(..., description="Course identifier (from JWT)")
    user_id: str = Field(..., description="User identifier (from JWT)")
    summary: Optional[str] = Field(None, description="Rolling summary (layer B), if any")
    summary_tokens: int = Field(0, description="Rough token estimate for the summary")
    history: List[ChatScopeMessageItem] = Field(
        default_factory=list,
        description="Layer A messages AFTER token-budget trimming",
    )
    history_message_count: int = Field(0, description="Number of trimmed history messages")
    history_tokens: int = Field(0, description="Rough token estimate for the trimmed history")
    history_max_tokens_budget: int = Field(
        ...,
        description="CHAT_HISTORY_MAX_TOKENS at request time, for reference",
    )
    question: Optional[str] = Field(
        None,
        description="The hypothetical question echoed back, if one was supplied",
    )
    composed_query: Optional[str] = Field(
        None,
        description="Full query_str /api/chat would build for `question`; null when no question was supplied",
    )


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
    course_id: str = Field(..., min_length=1, max_length=255, description="Course unique identifier")
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
