from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Iterator, Tuple, Dict, Literal, Union

from pypdf import PageObject, PdfReader

from rmdocs.struct.page import Page


class FileType:
    UNKNOWN = -1
    DOCUMENT = 'DocumentType'
    FOLDER = 'CollectionType'

    @staticmethod
    def valid_type(file_type: str) -> bool:
        return file_type in [FileType.DOCUMENT, FileType.FOLDER]


class Content:

    def __init__(self, src: Path, uuid: str, raw: Dict):
        self.src = src
        self.uuid = uuid
        self.raw = raw

    @staticmethod
    def from_file(src: Path, uuid: str, file_type: FileType) -> Optional[Content]:
        path = src.joinpath(uuid + ".content")
        if not path.exists():
            return None
        with path.open() as f:
            raw = json.load(f)
        if file_type == FileType.FOLDER:
            return ContentFolder(src, uuid, raw)
        elif file_type == FileType.DOCUMENT:
            return ContentFile(src, uuid, raw)
        return None

    def get_version(self) -> Optional[int]:
        raise NotImplementedError("This is an abstract class.")

    def test_assertion(self) -> Union[Literal[True], str]:
        # if the file is a document, the content file needs to have:
        # - the formatVersion
        # - the pageCount
        # - the pages info
        raise NotImplementedError("This is an abstract class")


class ContentFile(Content):

    def __init__(self, src: Path, uuid: str, raw: Dict):
        super().__init__(src, uuid, raw)

    def get_version(self) -> int:
        return self.raw["formatVersion"]

    def get_pages_count(self) -> int:
        return len(self.raw["cPages"]["pages"] if self.get_version() == 2 else self.raw["pages"])

    def iterate_pages(self, bg_pdf: Optional[PdfReader]) -> Iterator[Tuple[Optional[Page], Optional[PageObject]]]:
        for i in range(max(self.get_pages_count(), 0 if bg_pdf is None else len(bg_pdf.pages))):
            page = None
            bg = None
            if self.get_version() == 1:
                if i < len(self.raw["pages"]):
                    page_def = self.raw["pages"][i]
                    page = Page.from_file(self.src, self.uuid, page_def, page_def)

                if bg_pdf is not None and i < len(bg_pdf.pages):
                    bg = bg_pdf.pages[i]
            else:
                if i < len(self.raw["cPages"]["pages"]):
                    page_def = self.raw["cPages"]["pages"][i]
                    page = Page.from_file(self.src, self.uuid, page_def["id"], page_def)
                    if bg_pdf is not None and page.bg_pdf_page_idx is not None:
                        bg = bg_pdf.pages[page.bg_pdf_page_idx]
            yield page, bg

    def get_pages(self) -> Iterator[Page]:
        pages_data = self.raw["cPages"]["pages"] if self.get_version() == 2 else self.raw["pages"]

        for page_def in pages_data:
            if "deleted" not in page_def:
                yield Page.from_file(self.src, self.uuid,
                                     page_def if self.get_version() == 1 else page_def["id"], page_def)

    def test_assertion(self) -> Union[Literal[True], str]:
        if self.get_version() == 1:
            if not all([p in self.raw for p in ["formatVersion", "pageCount", "pages"]]):
                return "Missing attributes in .content file."
        elif self.get_version() == 2:
            if not all([p in self.raw for p in ["formatVersion", "pageCount", "cPages"]]) \
                and "pages" in self.raw["cPages"]:
                return "Missing attributes in .content file."
        else:
            return "This software is only compatible with content version 1 and 2."
        return True


class ContentFolder(Content):
    def __init__(self, src: Path, uuid: str, raw: Dict):
        super().__init__(src, uuid, raw)

    def get_version(self) -> Optional[int]:
        return None

    def test_assertion(self) -> Union[Literal[True], str]:
        return True
