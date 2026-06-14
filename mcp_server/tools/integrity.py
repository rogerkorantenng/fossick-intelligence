import hashlib
import time
from pathlib import Path


class EvidenceSpoliationError(Exception):
    """Raised when a forensic image is modified during analysis."""
    pass


def compute_sha256(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def assert_no_spoliation(file_path: str, original_hash: str) -> None:
    current_hash = compute_sha256(file_path)
    if current_hash != original_hash:
        raise EvidenceSpoliationError(
            f"Evidence integrity violated: {file_path}\n"
            f"  Original SHA-256: {original_hash}\n"
            f"  Current SHA-256:  {current_hash}"
        )


class EvidenceContext:
    """Context manager that verifies image integrity before and after tool execution."""

    def __init__(self, image_path: str):
        self.image_path = image_path
        self.hash_before: str = ""
        self.start_time: float = 0.0

    def __enter__(self):
        if Path(self.image_path).exists():
            self.hash_before = compute_sha256(self.image_path)
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.hash_before and Path(self.image_path).exists():
            assert_no_spoliation(self.image_path, self.hash_before)
        return False

    @property
    def duration_ms(self) -> int:
        return int((time.time() - self.start_time) * 1000)
