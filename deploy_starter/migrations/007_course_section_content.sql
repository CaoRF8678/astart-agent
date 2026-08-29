ALTER TABLE course_sections
ADD COLUMN content TEXT,
ADD COLUMN source_references JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE generation_section_results (
    generation_id VARCHAR(64) NOT NULL,
    module_order INTEGER NOT NULL,
    chapter_order INTEGER NOT NULL,
    section_order INTEGER NOT NULL,

    retrieval_queries JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieved_context TEXT NOT NULL DEFAULT '',
    retrieved_references JSONB NOT NULL DEFAULT '[]'::jsonb,

    draft_content TEXT,
    draft_cited_source_numbers JSONB NOT NULL DEFAULT '[]'::jsonb,

    final_content TEXT,
    final_references JSONB NOT NULL DEFAULT '[]'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        generation_id,
        module_order,
        chapter_order,
        section_order
    ),

    CONSTRAINT fk_generation_section_results_job
        FOREIGN KEY (generation_id)
        REFERENCES generation_jobs(generation_id)
        ON DELETE CASCADE,

    CONSTRAINT ck_generation_section_results_module_order
        CHECK (module_order >= 0),

    CONSTRAINT ck_generation_section_results_chapter_order
        CHECK (chapter_order >= 0),

    CONSTRAINT ck_generation_section_results_section_order
        CHECK (section_order >= 0)
);


INSERT INTO generation_stages (
    generation_id,
    stage,
    status
)
SELECT
    generation_id,
    'draft',
    'pending'
FROM generation_jobs
WHERE status IN ('pending', 'running')
ON CONFLICT DO NOTHING;

INSERT INTO generation_stages (
    generation_id,
    stage,
    status
)
SELECT
    generation_id,
    'final_check',
    'pending'
FROM generation_jobs
WHERE status IN ('pending', 'running')
ON CONFLICT DO NOTHING;