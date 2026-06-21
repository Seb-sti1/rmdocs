from __future__ import annotations

import io
import os
import shutil
import zipfile
from typing import List, overload, Literal, BinaryIO, IO, Any, Set, Optional


class AbstractPath:
    """Create an abstraction to interact with files or content of zip file indistinctively"""

    def name(self) -> str:
        raise NotImplementedError

    def join(self, *parts: str) -> AbstractPath:
        raise NotImplementedError

    def exists(self) -> bool:
        raise NotImplementedError

    def listdir(self) -> List[AbstractPath]:
        raise NotImplementedError

    @overload
    def open(self, mode: Literal["r", "rt", "tr"] = ..., **kwargs) -> io.TextIOWrapper: ...

    @overload
    def open(self, mode: Literal["rb", "br"], **kwargs) -> BinaryIO: ...

    @overload
    def open(self, mode: str, **kwargs) -> IO[Any]: ...

    def open(self, mode: str = "r", **kwargs) -> IO[Any]:
        raise NotImplementedError

    def copy(self, dst: str) -> None:
        raise NotImplementedError


class LocalPath(AbstractPath):
    """For real filesystem on the disk."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = os.path.normpath(path)

    def name(self) -> str:
        return os.path.basename(self.path)

    def join(self, *parts: str) -> LocalPath:
        return LocalPath(os.path.join(self.path, *parts))

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def listdir(self) -> List[LocalPath]:
        return [LocalPath(os.path.join(self.path, name)) for name in os.listdir(self.path)]

    def open(self, mode: str = "r", **kwargs):
        return open(self.path, mode, **kwargs)

    def copy(self, dst: str) -> None:
        shutil.copy2(self.path, dst)

    def __eq__(self, other):
        if not isinstance(other, ZipPath):
            return NotImplemented
        return self.path == other.path

    def __hash__(self):
        return hash(self.path)


class ZipPath(AbstractPath):
    """For file inside a zip."""

    def __init__(self, zf: zipfile.ZipFile, path: str = "/", index: Optional[Set[str]] = None) -> None:
        super().__init__()
        self.zf = zf
        self.path = path

        if index is not None:
            self.index = index
        else:
            self.index: Set[str] = set()
            for name in self.zf.namelist():
                self.index.add(f"/{name}".rstrip("/"))

    def name(self) -> str:
        return self.path.split("/")[-1]

    def join(self, *parts: str) -> ZipPath:
        return ZipPath(self.zf, os.path.join(self.path, *parts), self.index)

    def exists(self) -> bool:
        if self.path == "/":
            return True
        return self.path in self.index

    def listdir(self) -> List[ZipPath]:
        return [ZipPath(self.zf, path, self.index) for path in self.index if
                path.startswith(f"{self.path.rstrip('/')}/") and "/" not in path[len(self.path) + 1:]]

    def open(self, mode: str = "r", encoding: str = "utf-8", **kwargs):
        if set(mode) & {"w", "a", "x"}:
            raise PermissionError("ZipPath is read-only")
        binary = self.zf.open(self.path.strip("/"))
        if "b" in mode:
            return binary
        return io.TextIOWrapper(binary, encoding=encoding, **kwargs)

    def copy(self, dst: str) -> None:
        with self.open("rb") as src, open(dst, "wb") as out:
            shutil.copyfileobj(src, out)

    def __eq__(self, other):
        if not isinstance(other, ZipPath):
            return NotImplemented
        return self.path == other.path

    def __hash__(self):
        return hash(self.path)
