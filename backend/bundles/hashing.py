"""sha256 digests computed while members stream into the zip.

One pass, not two: a bundle's structure files are the bulk of its bytes, and hashing them
in a second pass would double the disk reads for no benefit. Every member goes through
``HashingWriter``, so the manifest's digest is of exactly the bytes that were archived.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator, TextIO

CHUNK_BYTES = 256 * 1024


@dataclass
class MemberDigest:
    size_bytes: int = 0
    sha256: str = ""


class HashingWriter(io.RawIOBase):
    """Binary file object that forwards to ``inner`` and hashes what passes through."""

    def __init__(self, inner: BinaryIO) -> None:
        self._inner = inner
        self._hash = hashlib.sha256()
        self._size = 0

    def writable(self) -> bool:
        return True

    def write(self, data) -> int:  # type: ignore[override]
        chunk = bytes(data)
        self._inner.write(chunk)
        self._hash.update(chunk)
        self._size += len(chunk)
        return len(chunk)

    def digest(self) -> MemberDigest:
        return MemberDigest(size_bytes=self._size, sha256=self._hash.hexdigest())


@contextmanager
def text_member(zf: zipfile.ZipFile, arcname: str) -> Iterator[tuple[TextIO, MemberDigest]]:
    """Open a text member for writing; the yielded digest is filled in on exit.

    newline="" because csv.writer emits its own line terminators.
    """
    result = MemberDigest()
    with zf.open(arcname, "w") as raw:
        hashing = HashingWriter(raw)  # type: ignore[arg-type]
        wrapper = io.TextIOWrapper(hashing, encoding="utf-8", newline="")
        try:
            yield wrapper, result
        finally:
            wrapper.flush()
            wrapper.detach()
            digest = hashing.digest()
            result.size_bytes = digest.size_bytes
            result.sha256 = digest.sha256


def write_file_member(zf: zipfile.ZipFile, arcname: str, path: Path) -> MemberDigest:
    """Copy a file on disk into the zip, hashing as it goes.

    Deliberately not ``zf.write(path)``: that gives no access to the bytes, so the digest
    would need a second read of the file.
    """
    with zf.open(arcname, "w") as raw:
        hashing = HashingWriter(raw)  # type: ignore[arg-type]
        with path.open("rb") as src:
            while True:
                chunk = src.read(CHUNK_BYTES)
                if not chunk:
                    break
                hashing.write(chunk)
        return hashing.digest()


def write_bytes_member(zf: zipfile.ZipFile, arcname: str, data: bytes) -> MemberDigest:
    with zf.open(arcname, "w") as raw:
        hashing = HashingWriter(raw)  # type: ignore[arg-type]
        hashing.write(data)
        return hashing.digest()
