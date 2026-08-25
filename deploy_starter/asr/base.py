from abc import ABC, abstractmethod
from schemas.asr import Transcript
class ASRService(ABC):
    @abstractmethod
    async def transcribe(
        self,
        *,
        storage_key: str,
    ) -> Transcript:
        raise NotImplementedError