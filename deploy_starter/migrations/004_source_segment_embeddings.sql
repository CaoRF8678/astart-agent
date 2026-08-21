ALTER TABLE source_segments
ADD COLUMN embedding VECTOR(1024);

ALTER TABLE source_segments
ADD COLUMN embedding_model VARCHAR(100);