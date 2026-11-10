"""Secure Model Artifact Management and Integrity Verification for OCR Engines.

Verifies model weights and character dictionaries against an approved cryptographic
manifest before engine initialization. Enforces strict zero-trust artifact identity,
path sanitization, and diagnostics.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from document_intelligence.core.config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE_BYTES = 64 * 1024  # 64 KB streaming buffer for checksum computation


class ModelArtifactError(RuntimeError):
    """Base exception for model artifact failures."""


class ModelArtifactNotFoundError(ModelArtifactError):
    """Raised when an approved model artifact or dictionary is missing from storage."""


class ModelArtifactCorruptError(ModelArtifactError):
    """Raised when an artifact checksum does not match the approved cryptographic manifest."""


class ModelArtifactSecurityError(ModelArtifactError):
    """Raised when model path violates filesystem or security constraints."""


@dataclass(frozen=True)
class ApprovedModelArtifact:
    """Cryptographic and architectural specification of an approved model artifact."""

    model_id: str
    model_version: str
    model_filename: str
    expected_model_sha256: str
    dictionary_filename: str
    expected_dictionary_sha256: str
    upstream_source: str
    upstream_revision: str
    license_evidence: str
    rec_img_shape: list[int] = field(default_factory=lambda: [3, 48, 320])
    default_use_cls: bool = False
    default_box_thresh: float = 0.3
    default_unclip_ratio: float = 1.6

    @property
    def model_sha256(self) -> str:
        return self.expected_model_sha256

    @property
    def dictionary_sha256(self) -> str:
        return self.expected_dictionary_sha256


# Authoritative manifest of approved OCR models
PP_OCRV5_DEVANAGARI = ApprovedModelArtifact(
    model_id="devanagari_PP-OCRv5_mobile_rec_infer",
    model_version="5.0.0-mobile",
    model_filename="devanagari_PP-OCRv5_mobile_rec_infer.onnx",
    expected_model_sha256="cb789212ce96c69d3e74728ae4309d179281d68cb3945d0616b67cafab41c986",
    dictionary_filename="devanagari_v5_dict.txt",
    expected_dictionary_sha256="f3ac932023e83fb0e995383957c8953cd3e506737308fe44cffab61549deadb3",
    upstream_source="https://huggingface.co/PaddlePaddle/devanagari_PP-OCRv5_mobile_rec_onnx",
    upstream_revision="main (commit 3febe46)",
    license_evidence="Apache-2.0 (PaddleOCR release)",
    rec_img_shape=[3, 48, 320],
    default_use_cls=False,
    default_box_thresh=0.3,
    default_unclip_ratio=1.6,
)

PP_OCRV4_LATIN_BASELINE = ApprovedModelArtifact(
    model_id="ch_PP-OCRv4_rec_infer",
    model_version="4.0.0",
    model_filename="ch_PP-OCRv4_rec_infer.onnx",
    expected_model_sha256="893c52402bc06a928baeb77d206f6b5795a468d6693a11b7dfb3cf8ad1be01c3",
    dictionary_filename="ppocr_keys_v1.txt",
    expected_dictionary_sha256="embedded",
    upstream_source="RapidAI/RapidOCR v1.4.4",
    upstream_revision="v1.4.4",
    license_evidence="Apache-2.0",
    rec_img_shape=[3, 48, 320],
    default_use_cls=True,
    default_box_thresh=0.5,
    default_unclip_ratio=1.6,
)

APPROVED_MODELS: dict[str, ApprovedModelArtifact] = {
    PP_OCRV5_DEVANAGARI.model_id: PP_OCRV5_DEVANAGARI,
    PP_OCRV4_LATIN_BASELINE.model_id: PP_OCRV4_LATIN_BASELINE,
}


@dataclass(frozen=True)
class VerifiedModelArtifact:
    """Verified model artifact with confirmed cryptographic integrity."""

    model_id: str
    model_version: str
    model_filename: str
    model_path: Path
    model_sha256: str
    dictionary_filename: str
    dictionary_path: Path
    dictionary_sha256: str
    license_evidence: str
    rec_img_shape: list[int]
    default_use_cls: bool
    default_box_thresh: float
    default_unclip_ratio: float

    def safe_provenance_metadata(self) -> dict[str, Any]:
        """Produce safe public provenance metadata containing ZERO local filesystem paths."""
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "model_filename": self.model_filename,
            "model_sha256": self.model_sha256,
            "character_dict_name": self.dictionary_filename,
            "model_artifacts": {
                "rec_model": self.model_sha256,
                "rec_dict": self.dictionary_sha256,
            },
            "license": self.license_evidence,
        }

    def to_safe_metadata(self) -> dict[str, Any]:
        """Alias for safe_provenance_metadata."""
        return self.safe_provenance_metadata()


class OcrModelArtifactManager:
    """Manages and cryptographically validates OCR model artifacts."""

    def __init__(
        self,
        model_dir: Path | str | None = None,
        models_dir: Path | str | None = None,
    ) -> None:
        target = model_dir or models_dir
        self._custom_model_dir = Path(target) if target else None

    def resolve_model_dir(self, custom_path: Path | None = None) -> Path:
        """Resolve the effective model storage directory with safe fallbacks."""
        if custom_path:
            return custom_path
        if self._custom_model_dir:
            return self._custom_model_dir

        # Check configured data directory first
        cfg_dir = getattr(settings, "ocr_model_dir", Path("./data/models/ocr"))
        if cfg_dir.exists():
            return cfg_dir

        # Check research POC location as development fallback
        poc_dir = Path("research/multilingual-ocr/poc/models")
        if poc_dir.exists():
            return poc_dir

        return cfg_dir

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute streaming SHA-256 digest of a file."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE_BYTES):
                hasher.update(chunk)
        return hasher.hexdigest().lower()

    def verify_artifact(
        self,
        artifact: ApprovedModelArtifact,
        custom_model_dir: Path | None = None,
    ) -> VerifiedModelArtifact:
        """Verify model weights and matching character dictionary against the manifest."""
        target_dir = self.resolve_model_dir(custom_model_dir)

        # 1. Resolve paths
        model_path = target_dir / artifact.model_filename
        dict_path = target_dir / artifact.dictionary_filename

        # 2. Check model file presence
        if not model_path.exists():
            raise ModelArtifactNotFoundError(
                f"Approved model artifact '{artifact.model_filename}' not found in '{target_dir.name}'. "
                f"Required model ID: '{artifact.model_id}' v{artifact.model_version}."
            )
        if not model_path.is_file():
            raise ModelArtifactSecurityError(
                f"Model artifact target '{artifact.model_filename}' is not a regular file."
            )

        # 3. Check dictionary file presence
        if not dict_path.exists():
            raise ModelArtifactNotFoundError(
                f"Approved character dictionary '{artifact.dictionary_filename}' not found in '{target_dir.name}'. "
                f"Required for model ID: '{artifact.model_id}'."
            )
        if not dict_path.is_file():
            raise ModelArtifactSecurityError(
                f"Character dictionary target '{artifact.dictionary_filename}' is not a regular file."
            )

        # 4. Verify model SHA-256
        actual_model_sha = self.compute_sha256(model_path)
        expected_model_sha = artifact.expected_model_sha256.lower()
        if actual_model_sha != expected_model_sha:
            raise ModelArtifactCorruptError(
                f"Model artifact '{artifact.model_filename}' hash mismatch: failed SHA-256 integrity verification. "
                f"Expected: '{expected_model_sha}', Got: '{actual_model_sha}'. "
                f"Artifact identity rejected for '{artifact.model_id}'."
            )

        # 5. Verify dictionary SHA-256
        actual_dict_sha = self.compute_sha256(dict_path)
        expected_dict_sha = artifact.expected_dictionary_sha256.lower()
        if actual_dict_sha != expected_dict_sha:
            raise ModelArtifactCorruptError(
                f"Character dictionary '{artifact.dictionary_filename}' hash mismatch: failed SHA-256 integrity verification. "
                f"Expected: '{expected_dict_sha}', Got: '{actual_dict_sha}'."
            )

        logger.info(
            f"Successfully verified OCR artifact '{artifact.model_id}' v{artifact.model_version} "
            f"(SHA256: {actual_model_sha[:12]}..., Dict SHA256: {actual_dict_sha[:12]}...)"
        )

        return VerifiedModelArtifact(
            model_id=artifact.model_id,
            model_version=artifact.model_version,
            model_filename=artifact.model_filename,
            model_path=model_path,
            model_sha256=actual_model_sha,
            dictionary_filename=artifact.dictionary_filename,
            dictionary_path=dict_path,
            dictionary_sha256=actual_dict_sha,
            license_evidence=artifact.license_evidence,
            rec_img_shape=artifact.rec_img_shape,
            default_use_cls=artifact.default_use_cls,
            default_box_thresh=artifact.default_box_thresh,
            default_unclip_ratio=artifact.default_unclip_ratio,
        )
