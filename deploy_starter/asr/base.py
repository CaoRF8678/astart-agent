from abc import ABC, abstractmethod
from schemas.asr import Transcript

class ASRServiceError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        
class ASRService(ABC):
    @abstractmethod
    async def transcribe(
        self,
        *,
        storage_key: str,
    ) -> Transcript:
        raise NotImplementedError