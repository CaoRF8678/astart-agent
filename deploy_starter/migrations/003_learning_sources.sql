CREATE TABLE learning_sources (
    file_id VARCHAR(64) PRIMARY KEY,

    course_id VARCHAR(64) NOT NULL,

    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(255) NOT NULL,
    size BIGINT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    storage_key TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_learning_sources_course
        FOREIGN KEY (course_id)
        REFERENCES courses(course_id)
        ON DELETE CASCADE,

    CONSTRAINT ck_learning_sources_size
        CHECK (size > 0)
);


CREATE INDEX idx_learning_sources_course_created_at
ON learning_sources (
    course_id,
    created_at DESC
);


CREATE TABLE source_segments (
    segment_id VARCHAR(64) PRIMARY KEY,

    file_id VARCHAR(64) NOT NULL,

    content TEXT NOT NULL,
    segment_order INTEGER NOT NULL,
    locator JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_source_segments_source
        FOREIGN KEY (file_id)
        REFERENCES learning_sources(file_id)
        ON DELETE CASCADE,

    CONSTRAINT ck_source_segments_order
        CHECK (segment_order >= 0),

    CONSTRAINT uq_source_segments_file_order
        UNIQUE (
            file_id,
            segment_order
        )
);