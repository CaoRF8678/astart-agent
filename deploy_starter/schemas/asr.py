from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    text: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker_id: str | None = None


class Transcript(BaseModel):
    text: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    segments: list[TranscriptSegment]