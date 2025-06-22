import json
import time
from typing import Any, Dict
from google.cloud import storage
from .logger import setup_logger


class GCSManager:
    """Simple wrapper around google.cloud.storage with retry and rate limiting."""

    def __init__(self, max_retries: int = 3, rate_limit: float = 0.2):
        self.client = storage.Client()
        self.max_retries = max_retries
        self.rate_limit = rate_limit
        self._last_call = 0.0
        self.logger = setup_logger(self.__class__.__name__)

    def _throttle(self):
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_call = time.time()

    def download_text(self, bucket_name: str, blob_name: str) -> str:
        for attempt in range(1, self.max_retries + 1):
            try:
                self._throttle()
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                return blob.download_as_text()
            except Exception as exc:
                self.logger.warning(
                    f"Attempt {attempt} failed to download {blob_name}: {exc}"
                )
                if attempt == self.max_retries:
                    raise
                time.sleep(2**attempt)

    def upload_json(self, bucket_name: str, blob_name: str, data: Dict[str, Any]):
        content = json.dumps(data, ensure_ascii=False, indent=2)
        for attempt in range(1, self.max_retries + 1):
            try:
                self._throttle()
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.upload_from_string(content, content_type="application/json")
                return
            except Exception as exc:
                self.logger.warning(
                    f"Attempt {attempt} failed to upload {blob_name}: {exc}"
                )
                if attempt == self.max_retries:
                    raise
                time.sleep(2**attempt)
