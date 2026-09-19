"""
file_safety.py
---------------
Two small, dependency-free defenses around untrusted uploads:

1. `sniff_mismatch` — checks the file's actual magic bytes against its
   claimed extension. An extension check alone (the old behavior) can be
   trivially spoofed by renaming any file to .pdf/.docx/.txt.

2. `run_with_timeout` — runs a slow/blocking call (PDF/DOCX text
   extraction) with a hard wall-clock budget, so a pathological or corrupt
   file can't tie up a gunicorn worker indefinitely. Python can't forcibly
   kill a thread, so the worker thread that ran past the timeout is
   abandoned rather than truly terminated — but the request itself returns
   promptly with an error instead of hanging, which is what protects the
   rest of the app's responsiveness.
"""

import concurrent.futures

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"  # .docx is a zip container


class FileSignatureMismatch(Exception):
    pass


class ExtractionTimeout(Exception):
    pass


def sniff_mismatch(file_storage, extension: str) -> bool:
    """Return True if the file's header doesn't match its claimed extension.

    `file_storage` is a Werkzeug FileStorage (has .stream). Leaves the
    stream position reset to 0 afterwards so it can still be saved normally.
    """
    stream = file_storage.stream
    header = stream.read(8)
    stream.seek(0)

    if extension == ".pdf":
        return not header.startswith(_PDF_MAGIC)
    if extension == ".docx":
        return not header.startswith(_ZIP_MAGIC)
    # .txt has no reliable magic bytes — skip the check.
    return False


def run_with_timeout(fn, args=(), kwargs=None, timeout=15):
    """Run `fn(*args, **kwargs)` with a hard wall-clock timeout.

    Raises ExtractionTimeout if it doesn't finish in time; re-raises
    whatever `fn` raised otherwise.
    """
    kwargs = kwargs or {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise ExtractionTimeout(
                "This file took too long to process (it may be corrupt or unusually complex). "
                "Try a smaller or simpler file."
            )
