"""
Course Configuration Service
=============================

Service layer for managing course configurations with caching.
Handles CRUD operations for course-to-table mappings stored in Supabase.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)


# ============================================================================
# In-Memory Cache
# ============================================================================

class CourseConfigCache:
    """Simple in-memory cache with TTL for course configurations"""

    def __init__(self, ttl_seconds: int = 300):
        """Initialize cache with TTL (default 5 minutes)"""
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, course_id: str) -> Optional[Dict[str, Any]]:
        """Get course config from cache"""
        if course_id not in self.cache:
            return None

        # Check if expired
        if datetime.utcnow() - self.cache_timestamps[course_id] > self.ttl:
            self.invalidate(course_id)
            return None

        return self.cache[course_id]

    def set(self, course_id: str, config: Dict[str, Any]) -> None:
        """Set course config in cache"""
        self.cache[course_id] = config
        self.cache_timestamps[course_id] = datetime.utcnow()

    def invalidate(self, course_id: str) -> None:
        """Invalidate specific course config"""
        self.cache.pop(course_id, None)
        self.cache_timestamps.pop(course_id, None)

    def clear(self) -> None:
        """Clear entire cache"""
        self.cache.clear()
        self.cache_timestamps.clear()


# Global cache instance
_cache = CourseConfigCache(ttl_seconds=300)  # 5 minutes TTL


# ============================================================================
# Course Configuration Service
# ============================================================================

class CourseConfigService:
    """Service for managing course configurations"""

    def __init__(self):
        """Initialize service with Supabase credentials from environment"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.table_name = "course_configurations"

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        self.client = httpx.Client(headers=self.headers, timeout=30.0)
        logger.info(f"✅ CourseConfigService initialized: {self.supabase_url}")

    def get_course_config(self, course_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get course configuration by course_id.

        Args:
            course_id: The course identifier
            use_cache: Whether to use cached config (default: True)

        Returns:
            Course configuration dict or None if not found

        Raises:
            httpx.HTTPError: If API request fails
        """
        # Check cache first
        if use_cache:
            cached = _cache.get(course_id)
            if cached:
                logger.debug(f"📦 Course config for '{course_id}' retrieved from cache")
                return cached

        # Fetch from Supabase
        url = f"{self.supabase_url}/rest/v1/{self.table_name}"
        params = {
            "course_id": f"eq.{course_id}",
            "active": "eq.true",
            "select": "*"
        }

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            if not data:
                logger.warning(f"⚠️  Course config not found: {course_id}")
                return None

            config = data[0]  # Get first result
            _cache.set(course_id, config)
            logger.info(f"✅ Course config retrieved for: {course_id}")
            return config

        except httpx.HTTPError as e:
            logger.error(f"❌ Error fetching course config for {course_id}: {e}")
            raise

    def list_course_configs(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all course configurations.

        Args:
            active_only: If True, only return active courses (default: True)

        Returns:
            List of course configuration dicts

        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"{self.supabase_url}/rest/v1/{self.table_name}"
        params = {"select": "*", "order": "created_at.desc"}

        if active_only:
            params["active"] = "eq.true"

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            logger.info(f"✅ Retrieved {len(data)} course configs")
            return data

        except httpx.HTTPError as e:
            logger.error(f"❌ Error listing course configs: {e}")
            raise

    def create_course_config(self, course_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new course configuration.

        Args:
            course_data: Course configuration data

        Returns:
            Created course configuration dict

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If course_id already exists
        """
        url = f"{self.supabase_url}/rest/v1/{self.table_name}"

        try:
            response = self.client.post(url, json=course_data)
            response.raise_for_status()

            data = response.json()
            created_config = data[0] if isinstance(data, list) else data

            # Cache the new config
            course_id = created_config.get("course_id")
            if course_id:
                _cache.set(course_id, created_config)

            logger.info(f"✅ Course config created: {course_id}")
            return created_config

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                logger.error(f"❌ Course ID already exists: {course_data.get('course_id')}")
                raise ValueError(f"Course ID '{course_data.get('course_id')}' already exists")
            logger.error(f"❌ Error creating course config: {e}")
            raise

    def update_course_config(
        self,
        course_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing course configuration.

        Args:
            course_id: The course identifier
            update_data: Fields to update

        Returns:
            Updated course configuration dict or None if not found

        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"{self.supabase_url}/rest/v1/{self.table_name}"
        params = {"course_id": f"eq.{course_id}"}

        try:
            response = self.client.patch(url, params=params, json=update_data)
            response.raise_for_status()

            data = response.json()
            if not data:
                logger.warning(f"⚠️  Course config not found for update: {course_id}")
                return None

            updated_config = data[0] if isinstance(data, list) else data

            # Invalidate cache
            _cache.invalidate(course_id)

            logger.info(f"✅ Course config updated: {course_id}")
            return updated_config

        except httpx.HTTPError as e:
            logger.error(f"❌ Error updating course config {course_id}: {e}")
            raise

    def delete_course_config(self, course_id: str, soft_delete: bool = True) -> bool:
        """
        Delete or deactivate a course configuration.

        Args:
            course_id: The course identifier
            soft_delete: If True, set active=false; if False, delete record (default: True)

        Returns:
            True if successful, False if not found

        Raises:
            httpx.HTTPError: If API request fails
        """
        if soft_delete:
            # Soft delete: just set active=false
            result = self.update_course_config(course_id, {"active": False})
            if result:
                logger.info(f"✅ Course config deactivated: {course_id}")
                return True
            return False
        else:
            # Hard delete: remove record
            url = f"{self.supabase_url}/rest/v1/{self.table_name}"
            params = {"course_id": f"eq.{course_id}"}

            try:
                response = self.client.delete(url, params=params)
                response.raise_for_status()

                # Invalidate cache
                _cache.invalidate(course_id)

                logger.info(f"✅ Course config deleted: {course_id}")
                return True

            except httpx.HTTPError as e:
                logger.error(f"❌ Error deleting course config {course_id}: {e}")
                raise

    def get_fallback_config(self) -> Dict[str, Any]:
        """
        Get fallback configuration from environment variables.
        Used when no course_id is provided or for backward compatibility.

        Returns:
            Fallback course configuration dict
        """
        return {
            "course_id": "default",
            "course_name": "Default Course",
            "course_slug": "default",
            "table_name": os.getenv("SUPABASE_TABLE_NAME", ""),
            "rpc_function": os.getenv("SUPABASE_RPC_FUNCTION", ""),
            "active": True,
            "description": "Fallback configuration from environment variables",
            "metadata": {}
        }

    def clear_cache(self) -> None:
        """Clear the entire course config cache"""
        _cache.clear()
        logger.info("✅ Course config cache cleared")


# ============================================================================
# Global Service Instance
# ============================================================================

# Singleton instance
_service: Optional[CourseConfigService] = None


def get_course_config_service() -> CourseConfigService:
    """
    Get or create the global CourseConfigService instance.

    Returns:
        CourseConfigService instance
    """
    global _service
    if _service is None:
        _service = CourseConfigService()
    return _service
