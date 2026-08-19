--SQL Migration（数据库迁移脚本）
CREATE TABLE generation_jobs (
    generation_id VARCHAR(64) PRIMARY KEY, 

    user_id VARCHAR(128) NOT NULL,

    status VARCHAR(32) NOT NULL,

    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,

    worker_id VARCHAR(128),

    learning_brief JSONB NOT NULL,

    research_result JSONB,

    outline_v1 JSONB,

    critique_result JSONB,

    final_outline JSONB,

    error_code VARCHAR(128),

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    started_at TIMESTAMPTZ,

    finished_at TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_generation_jobs_status   --约束
        CHECK (
            status IN (
                'pending',
                'running',
                'completed',
                'failed',
                'cancelled'
            )
        )
);

CREATE INDEX idx_generation_jobs_status_created_at
ON generation_jobs (status, created_at);

CREATE INDEX idx_generation_jobs_user_created_at
ON generation_jobs (user_id, created_at);

CREATE TABLE generation_stages (
    generation_id VARCHAR(64) NOT NULL,

    stage VARCHAR(32) NOT NULL,

    status VARCHAR(32) NOT NULL DEFAULT 'pending',

    attempt_count INTEGER NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ,

    finished_at TIMESTAMPTZ,

    error_code VARCHAR(128),

    error_message TEXT,

    PRIMARY KEY (generation_id, stage),

    CONSTRAINT fk_generation_stage_job
        FOREIGN KEY (generation_id)
        REFERENCES generation_jobs(generation_id) --关联到另外一个表
        ON DELETE CASCADE, --级联删除

    CONSTRAINT ck_generation_stage_attempt
        CHECK (attempt_count >= 0),


    CONSTRAINT ck_generation_stage_status
        CHEck (
            status IN(
                'pending',
                'running',
                'completed',
                'failed',
                'cancelled'
            )
        ),
    CONSTRAINT ck_generation_stage_name
        CHECK (
            stage IN (
                'research',
                'outline',
                'critique',
                'revision',
                'draft',
                'final_check'
            )
    )
);