"""Subprocess worker executing pdf-forensics-kit in an isolated child process."""

import argparse
import json
import sys
from pathlib import Path

# Ensure pdfforensics is available: first try installed package, then fallback to local clone
try:
    import pdfforensics  # noqa: F401
except ImportError:

    def _find_upstream_src() -> Path | None:
        current = Path(__file__).resolve()
        for parent in current.parents:
            candidate = parent / "upstream" / "pdf-forensics" / "pdf-forensics-kit" / "src"
            if candidate.exists() and (candidate / "pdfforensics").is_dir():
                return candidate
        return None

    _upstream_src = _find_upstream_src()
    if _upstream_src and str(_upstream_src) not in sys.path:
        sys.path.insert(0, str(_upstream_src))


def _sanitize_path(text: str, snapshot_path: str) -> str:
    """Strip local filesystem paths from error messages and logs."""
    return text.replace(snapshot_path, "<redacted_snapshot_path>")


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF Structural Forensics Subprocess Worker")
    parser.add_argument("--snapshot", required=True, help="Path to verified analysis snapshot")
    parser.add_argument("--options", default="{}", help="JSON serialized options dict")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists() or not snapshot_path.is_file():
        out = {
            "success": False,
            "error_type": "FileNotFoundError",
            "error_message": "Analysis snapshot file missing or unreadable.",
        }
        sys.stdout.write(json.dumps(out))
        sys.exit(1)

    try:
        options_dict = json.loads(args.options)
    except Exception:
        options_dict = {}

    try:
        from pdfforensics import capture, document
        from pdfforensics.engine import analyze_file

        opts = document.Options(
            max_bytes=int(options_dict.get("max_bytes", 50 * 1024 * 1024)),
            external_tools=bool(options_dict.get("external_tools", False)),
            online_revocation=bool(options_dict.get("online_revocation", False)),
        )

        try:
            report = analyze_file(snapshot_path, options=opts)
            report_dict = report.to_dict()

            # Enforce bounded collection sizes
            findings = report_dict.get("findings", [])
            if len(findings) > 500:
                report_dict["findings"] = findings[:500]
                report_dict["findings"].append(
                    {
                        "id": "system.truncated",
                        "category": "structure",
                        "title": "Findings Truncated",
                        "explanation": "Observed findings exceeded safety threshold of 500 items.",
                        "severity": "info",
                        "confidence": "high",
                    }
                )

            out = {
                "success": True,
                "report": report_dict,
            }
            sys.stdout.write(json.dumps(out))
            sys.exit(0)

        except capture.InputError as exc:
            msg = _sanitize_path(str(exc), str(snapshot_path))
            is_encrypted = "encrypted" in msg.lower() or "password" in msg.lower()
            out = {
                "success": False,
                "error_type": "PdfEncryptedException" if is_encrypted else "PdfParsingException",
                "error_message": msg[:2000],
                "is_encrypted": is_encrypted,
            }
            sys.stdout.write(json.dumps(out))
            sys.exit(0)

    except Exception as exc:
        msg = _sanitize_path(f"{type(exc).__name__}: {exc}", str(snapshot_path))
        is_encrypted = "password" in type(exc).__name__.lower() or "encrypted" in str(exc).lower()
        out = {
            "success": False,
            "error_type": "PdfEncryptedException" if is_encrypted else type(exc).__name__,
            "error_message": msg[:2000],
            "is_encrypted": is_encrypted,
        }
        sys.stdout.write(json.dumps(out))
        sys.exit(0)


if __name__ == "__main__":
    main()
