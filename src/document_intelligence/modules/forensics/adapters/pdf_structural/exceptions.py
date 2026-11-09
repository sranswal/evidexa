"""Exceptions specific to the PDF structural forensics adapter."""

from document_intelligence.core.exceptions import ForensicException


class PdfParsingException(ForensicException):
    """Raised when PDF structure parsing encounters a fatal error."""

    pass


class PdfEncryptedException(PdfParsingException):
    """Raised when PDF requires a password or has unsupported encryption."""

    pass


class PdfTimeoutException(PdfParsingException):
    """Raised when PDF parsing exceeds the allocated processing timeout."""

    pass
