CREATE TABLE courses (
    course_id VARCHAR(64) PRIMARY KEY,

    user_id VARCHAR(128) NOT NULL,

    generation_id VARCHAR(64) NOT NULL,

    outline JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_courses_generation_job
        FOREIGN KEY (generation_id)
        REFERENCES generation_jobs(generation_id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_courses_generation_id
        UNIQUE (generation_id)
);

CREATE INDEX idx_courses_user_created_at
ON courses (user_id, created_at DESC);


CREATE TABLE course_sections (
    section_id VARCHAR(64) PRIMARY KEY,

    course_id VARCHAR(64) NOT NULL,

    module_title TEXT NOT NULL,

    chapter_title TEXT NOT NULL,

    title TEXT NOT NULL,

    module_order INTEGER NOT NULL,

    chapter_order INTEGER NOT NULL,

    section_order INTEGER NOT NULL,

    estimated_minutes INTEGER NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_course_sections_course
        FOREIGN KEY (course_id)
        REFERENCES courses(course_id)
        ON DELETE CASCADE,

    CONSTRAINT ck_course_sections_module_order
        CHECK (module_order >= 0),

    CONSTRAINT ck_course_sections_chapter_order
        CHECK (chapter_order >= 0),

    CONSTRAINT ck_course_sections_section_order
        CHECK (section_order >= 0),

    CONSTRAINT ck_course_sections_estimated_minutes
        CHECK (estimated_minutes > 0),

    CONSTRAINT uq_course_sections_position
        UNIQUE (
            course_id,
            module_order,
            chapter_order,
            section_order
        )
);

CREATE INDEX idx_course_sections_course_order
ON course_sections (
    course_id,
    module_order,
    chapter_order,
    section_order
);