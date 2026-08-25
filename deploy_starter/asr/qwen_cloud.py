import asyncio
import json
from http import HTTPStatus
from urllib import request

import dashscope
from dashscope.audio.asr import Transcription

from asr.base import ASRService, ASRServiceError
from core.config import config
from schemas.asr import Transcript, TranscriptSegment
from storage.base import FileStorage, FileStorageError


class QwenCloudASRService(ASRService):
    def __init__(
        self,
        *,
        storage: FileStorage,
    ) -> None:
        self.storage = storage
        self.api_key = config.get("ASR_API_KEY")
        self.model_name = config.get(
            "ASR_MODEL",
            "qwen-audio-3.0-asr-flash-filetrans",
        )
        self.base_http_api_url = config.get(
            "ASR_BASE_HTTP_API_URL"
        )
        self.poll_interval_seconds = float(
            config.get(
                "ASR_POLL_INTERVAL_SECONDS",
                3,
            )
        )
        self.signed_url_expires_seconds = int(
            config.get(
                "OSS_SIGNED_URL_EXPIRES_SECONDS",
                21600,
            )
        )
        raw_hints = str(
            config.get(
                "ASR_LANGUAGE_HINTS",
                "zh,en",
            )
        )
        self.language_hints = [
            item.strip()
            for item in raw_hints.split(",")
            if item.strip()
        ]
        self.diarization_enabled = bool(
            config.get(
                "ASR_DIARIZATION_ENABLED",
                False,
            )
        )

        if not self.api_key:
            raise ASRServiceError(
                code="ASR_API_KEY_MISSING",
                message=(
                    "ASR_API_KEY is not configured."
                ),
            )

        if not self.base_http_api_url:
            raise ASRServiceError(
                code="ASR_BASE_URL_MISSING",
                message=(
                    "ASR_BASE_HTTP_API_URL is not configured."
                ),
            )

    def _run_with_dashscope_config(
        self,
        callback,
    ):
        old_api_key = getattr(
            dashscope,
            "api_key",
            None,
        )
        old_base_url = getattr(
            dashscope,
            "base_http_api_url",
            None,
        )

        try:
            dashscope.api_key = self.api_key
            dashscope.base_http_api_url = (
                self.base_http_api_url
            )
            return callback()
        finally:
            dashscope.api_key = old_api_key
            dashscope.base_http_api_url = old_base_url

    def _submit_task(
        self,
        audio_url: str,
    ):
        return self._run_with_dashscope_config(
            lambda: Transcription.async_call(
                model=self.model_name,
                file_urls=[audio_url],
                language_hints=self.language_hints,
                diarization_enabled=(
                    self.diarization_enabled
                ),
            )
        )

    def _fetch_task(
        self,
        task_id: str,
    ):
        return self._run_with_dashscope_config(
            lambda: Transcription.fetch(
                task=task_id
            )
        )

    @staticmethod
    def _download_json(
        url: str,
    ) -> dict:
        with request.urlopen(
            url,
            timeout=60,
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    @staticmethod
    def _normalize_result(
        payload: dict,
    ) -> Transcript:
        properties = payload.get(
            "properties",
            {},
        )
        duration_ms = int(
            properties.get(
                "original_duration_in_milliseconds",
                0,
            )
            or 0
        )

        transcript_texts: list[str] = []
        segments: list[TranscriptSegment] = []

        for transcript in payload.get(
            "transcripts",
            [],
        ):
            transcript_text = str(
                transcript.get("text", "")
            ).strip()
            if transcript_text:
                transcript_texts.append(
                    transcript_text
                )

            for sentence in transcript.get(
                "sentences",
                [],
            ):
                text = str(
                    sentence.get("text", "")
                ).strip()
                if not text:
                    continue

                try:
                    start_ms = int(
                        sentence["begin_time"]
                    )
                    end_ms = int(
                        sentence["end_time"]
                    )
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    raise ASRServiceError(
                        code="ASR_RESULT_INVALID",
                        message=(
                            "ASR sentence timestamp is invalid."
                        ),
                    ) from exc

                if end_ms < start_ms:
                    raise ASRServiceError(
                        code="ASR_RESULT_INVALID",
                        message=(
                            "ASR sentence end time precedes start time."
                        ),
                    )

                raw_speaker = sentence.get(
                    "speaker_id"
                )

                segments.append(
                    TranscriptSegment(
                        text=text,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        speaker_id=(
                            str(raw_speaker)
                            if raw_speaker is not None
                            else None
                        ),
                    )
                )

        if not segments:
            raise ASRServiceError(
                code="ASR_RESULT_EMPTY",
                message=(
                    "ASR returned no timestamped sentences."
                ),
            )

        segments.sort(
            key=lambda item: (
                item.start_ms,
                item.end_ms,
            )
        )

        full_text = "\n".join(
            transcript_texts
        ).strip()
        if not full_text:
            full_text = "\n".join(
                segment.text
                for segment in segments
            )

        return Transcript(
            text=full_text,
            duration_ms=duration_ms,
            segments=segments,
        )

    async def transcribe(
        self,
        *,
        storage_key: str,
    ) -> Transcript:
        try:
            audio_url = await self.storage.create_signed_url(
                storage_key,
                expires_seconds=(
                    self.signed_url_expires_seconds
                ),
            )
        except FileStorageError as exc:
            raise ASRServiceError(
                code="ASR_AUDIO_URL_FAILED",
                message=(
                    "Failed to create audio access URL."
                ),
            ) from exc

        try:
            response = await asyncio.to_thread(
                self._submit_task,
                audio_url,
            )
        except Exception as exc:
            raise ASRServiceError(
                code="ASR_SUBMIT_FAILED",
                message=(
                    "Failed to submit ASR task."
                ),
            ) from exc

        if response.status_code != HTTPStatus.OK:
            raise ASRServiceError(
                code="ASR_SUBMIT_FAILED",
                message=(
                    f"ASR submit failed: "
                    f"{response.code}: "
                    f"{response.message}"
                ),
            )

        task_id = response.output.task_id

        while True:
            await asyncio.sleep(
                self.poll_interval_seconds
            )

            try:
                response = await asyncio.to_thread(
                    self._fetch_task,
                    task_id,
                )
            except Exception as exc:
                raise ASRServiceError(
                    code="ASR_POLL_FAILED",
                    message=(
                        "Failed to query ASR task."
                    ),
                ) from exc

            if response.status_code != HTTPStatus.OK:
                raise ASRServiceError(
                    code="ASR_POLL_FAILED",
                    message=(
                        f"ASR query failed: "
                        f"{response.code}: "
                        f"{response.message}"
                    ),
                )

            task_status = (
                response.output.task_status
            )

            if task_status == "SUCCEEDED":
                break

            if task_status == "FAILED":
                raise ASRServiceError(
                    code="ASR_TASK_FAILED",
                    message=(
                        "ASR task reported FAILED."
                    ),
                )

        results = list(
            response.output["results"]
        )
        if len(results) != 1:
            raise ASRServiceError(
                code="ASR_RESULT_INVALID",
                message=(
                    "ASR result count is invalid."
                ),
            )

        result = results[0]
        if result.get("subtask_status") != "SUCCEEDED":
            raise ASRServiceError(
                code="ASR_TASK_FAILED",
                message=(
                    "ASR file subtask failed."
                ),
            )

        transcription_url = result.get(
            "transcription_url"
        )
        if not transcription_url:
            raise ASRServiceError(
                code="ASR_RESULT_INVALID",
                message=(
                    "ASR result URL is missing."
                ),
            )

        try:
            payload = await asyncio.to_thread(
                self._download_json,
                transcription_url,
            )
        except Exception as exc:
            raise ASRServiceError(
                code="ASR_RESULT_DOWNLOAD_FAILED",
                message=(
                    "Failed to download ASR result."
                ),
            ) from exc

        return self._normalize_result(
            payload
        )