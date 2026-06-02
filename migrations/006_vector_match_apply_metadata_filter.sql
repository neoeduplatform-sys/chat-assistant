CREATE OR REPLACE FUNCTION public.vector_match_apply_metadata_filter(
    doc_metadata jsonb,
    filter jsonb
)
RETURNS boolean
LANGUAGE plpgsql STABLE AS $$
BEGIN
    RETURN CASE
        -- If filter is null or empty, apply no filter (return true)
        WHEN filter IS NULL OR filter = '{}'::jsonb THEN TRUE

        -- Filter for documents that MUST have a non-empty topic_id
        WHEN filter ? 'has_topic_id' AND (filter ->> 'has_topic_id')::boolean = TRUE THEN
            doc_metadata ? 'topic_id'
            AND NULLIF(BTRIM(doc_metadata ->> 'topic_id'), '') IS NOT NULL

        -- Filter for documents that MUST NOT have a topic_id (or it's empty/null)
        WHEN filter ? 'has_topic_id' AND (filter ->> 'has_topic_id')::boolean = FALSE THEN
            NOT (doc_metadata ? 'topic_id')
            OR NULLIF(BTRIM(doc_metadata ->> 'topic_id'), '') IS NULL

        -- Filter for documents that match a specific topic_id value
        WHEN filter ? 'topic_id' THEN
            doc_metadata ->> 'topic_id' = filter ->> 'topic_id'

        -- Default case: if no known filter keys, apply no filter (return true)
        ELSE TRUE
    END;
END;
$$;