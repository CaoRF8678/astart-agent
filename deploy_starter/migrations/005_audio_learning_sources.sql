ALTER TABLE learning_sources
ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'ready',
ADD COLUMN worker_id VARCHAR(128),
ADD COLUMN processing_started_at TIMESTAMPTZ,
ADD COLUMN heartbeat_at TIMESTAMPTZ,
ADD COLUMN finished_at TIMESTAMPTZ,
ADD COLUMN error_code VARCHAR(100),
ADD COLUMN error_message TEXT,
ADD COLUMN transcript_storage_key TEXT;

ALTER TABLE learning_sources
ADD CONSTRAINT ck_learning_sources_status
CHECK (
    status IN (
        'pending',
        'processing',
        'ready',
        'failed'
    )
);

UPDATE learning_sources
SET finished_at = created_at
WHERE status = 'ready'
  AND finished_at IS NULL;

CREATE INDEX idx_learning_sources_pending_created_at
ON learning_sources (created_at)
WHERE status = 'pending';

CREATE INDEX idx_learning_sources_processing_heartbeat
ON learning_sources (heartbeat_at)
WHERE status = 'processing';