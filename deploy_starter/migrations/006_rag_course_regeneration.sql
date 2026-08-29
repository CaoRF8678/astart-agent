ALTER TABLE generation_jobs
ADD COLUMN target_course_id VARCHAR(64);

ALTER TABLE generation_jobs
ADD CONSTRAINT fk_generation_jobs_target_course
FOREIGN KEY (target_course_id)
REFERENCES courses(course_id)
ON DELETE SET NULL;

CREATE INDEX idx_generation_jobs_target_course_created_at
ON generation_jobs (
    target_course_id,
    created_at DESC
)
WHERE target_course_id IS NOT NULL;

CREATE UNIQUE INDEX uq_generation_jobs_active_target_course
ON generation_jobs (target_course_id)
WHERE target_course_id IS NOT NULL
  AND status IN ('pending', 'running');