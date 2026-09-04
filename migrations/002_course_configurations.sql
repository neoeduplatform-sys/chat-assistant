-- ============================================================================
-- Migration 002: Course Configurations Table
-- ============================================================================
-- Purpose: Store mappings between course_id and Supabase table/RPC configurations
-- This enables multi-tenant course support with dynamic table switching
--
-- Usage:
-- 1. Run this script in Supabase SQL Editor
-- 2. Insert your course configurations via API or manually
-- ============================================================================

-- Create course_configurations table
CREATE TABLE IF NOT EXISTS course_configurations (
    id BIGSERIAL PRIMARY KEY,
    course_id VARCHAR(255) UNIQUE NOT NULL,
    course_name VARCHAR(500) NOT NULL,
    course_slug VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    rpc_function VARCHAR(255) NOT NULL,
    active BOOLEAN DEFAULT true,
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_course_config_course_id
    ON course_configurations(course_id);

CREATE INDEX IF NOT EXISTS idx_course_config_active
    ON course_configurations(active);

CREATE INDEX IF NOT EXISTS idx_course_config_slug
    ON course_configurations(course_slug);

-- Add comments for documentation
COMMENT ON TABLE course_configurations IS 'Stores course-to-table mappings for multi-tenant vector store';
COMMENT ON COLUMN course_configurations.course_id IS 'Unique identifier for the course (e.g., course_123)';
COMMENT ON COLUMN course_configurations.course_name IS 'Human-readable name of the course';
COMMENT ON COLUMN course_configurations.course_slug IS 'URL-friendly slug for the course';
COMMENT ON COLUMN course_configurations.table_name IS 'Supabase table name where vectors are stored';
COMMENT ON COLUMN course_configurations.rpc_function IS 'Supabase RPC function for vector search';
COMMENT ON COLUMN course_configurations.active IS 'Whether this course is active and available';
COMMENT ON COLUMN course_configurations.metadata IS 'Additional course metadata (flexible JSONB)';

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_course_config_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update updated_at
DROP TRIGGER IF EXISTS trigger_update_course_config_timestamp ON course_configurations;
CREATE TRIGGER trigger_update_course_config_timestamp
    BEFORE UPDATE ON course_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_course_config_updated_at();

-- ============================================================================
-- Optional: Insert default course from existing .env configuration
-- ============================================================================
-- Uncomment and customize the values below to migrate your existing setup
-- Replace the placeholders with your actual table_name and rpc_function
--
-- INSERT INTO course_configurations (
--     course_id,
--     course_name,
--     course_slug,
--     table_name,
--     rpc_function,
--     active,
--     description
-- ) VALUES (
--     'default',
--     'Default Course',
--     'default',
--     'ec0241_gemi_test',                    -- Replace with your SUPABASE_TABLE_NAME
--     'match_ec0241_gemi_test',              -- Replace with your SUPABASE_RPC_FUNCTION
--     true,
--     'Default course migrated from .env configuration'
-- )
-- ON CONFLICT (course_id) DO NOTHING;

-- ============================================================================
-- Example: Insert sample courses for testing
-- ============================================================================
-- Uncomment to create sample courses

-- INSERT INTO course_configurations (
--     course_id,
--     course_name,
--     course_slug,
--     table_name,
--     rpc_function,
--     active,
--     description,
--     metadata
-- ) VALUES
-- (
--     'course_mant_mec',
--     'Mantenimiento Mecánico Automotriz',
--     'mantenimiento-mecanico',
--     'course_mant_mec_vectors',
--     'match_course_mant_mec_vectors',
--     true,
--     'Curso de mantenimiento mecánico automotriz',
--     '{"instructor": "John Doe", "level": "intermediate"}'::jsonb
-- ),
-- (
--     'course_elect_auto',
--     'Electrónica Automotriz',
--     'electronica-automotriz',
--     'course_elect_auto_vectors',
--     'match_course_elect_auto_vectors',
--     true,
--     'Curso de electrónica y sistemas automotrices',
--     '{"instructor": "Jane Smith", "level": "advanced"}'::jsonb
-- )
-- ON CONFLICT (course_id) DO NOTHING;

-- ============================================================================
-- Verification queries
-- ============================================================================
-- Run these to verify the table was created correctly

-- List all course configurations
-- SELECT * FROM course_configurations;

-- Count active courses
-- SELECT COUNT(*) as active_courses FROM course_configurations WHERE active = true;

-- Get course config by ID
-- SELECT * FROM course_configurations WHERE course_id = 'default';
