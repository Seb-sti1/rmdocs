import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Iterator, Dict, Literal, List

from rmdocs.assertion import AssertionException, MissingAttribute, UnknownValue
from rmdocs.io import AbstractPath

"""
Here is a list and partial description of the files in the /home/root/.local/share/remarkable/xochitl/ of the 
reMarkable. `[uuid]` represents an uuid v4.

- .tree: TBD
- [uuid].local: TBD
- [uuid].content: Contains information on the actual content (like pages, page count, etc)
- [uuid].metadata: Contains the metadata (like the name, parent file, etc)
- [uuid].pagedata: TBD
- [uuid].pdf: The background PDF (if any)
- [uuid]/: The folder containing the pages
    - [page uuid].rm: reMarkable binary files
    - [page uuid]-metadata.json: TBD
- [uuid].thumbnails/: The folder containing PNG of the pages (probably used for preview)
- [uuid].highlights/: TBD
- [uuid].textconversion/: TBD
"""

logger = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"([a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12})\.?.*")
RM_VERSION_HEADER = "reMarkable .lines file, version="
KNOWN_FILE_EXTENSIONS = ["tombstone", "local", "metadata", "content", "pagedata", "pdf", "dirty"]
KNOWN_FOLDER_EXTENSIONS = ["thumbnails", "highlights", "textconversion", "RM_FOLDER"]


class FileType(Enum):
    DOCUMENT = 'DocumentType'
    COLLECTION = 'CollectionType'


class PageVersion(Enum):
    V6 = 6
    V5 = 5
    V3 = 3

    def __str__(self):
        return {PageVersion.V6: "6", PageVersion.V5: "5", PageVersion.V3: "3"}[self]


VALID_VERSIONS: list[PageVersion] = [PageVersion.V6, PageVersion.V5, PageVersion.V3]


@dataclass
class RMPage:
    path: AbstractPath
    file_uuid: str
    page_uuid: str
    template: Optional[str]
    bg_pdf_page_idx: Optional[int]
    version: Optional[PageVersion]  # None if .rm file does not exist


@dataclass
class File:
    uuid: str
    name: str
    type: FileType
    parent_uuid: str
    src: AbstractPath
    bg_path: Optional[AbstractPath]
    pages: Optional[List[RMPage]]  # None for a folder


def parse_page_version(path: AbstractPath) -> PageVersion:
    headers = {v: RM_VERSION_HEADER + str(v) for v in VALID_VERSIONS}
    with path.open('rb') as f:
        file_header = f.read(max([len(headers[v]) for v in headers]))
        for v in headers:
            h = headers[v]
            if file_header.startswith(h.encode('ascii')):
                return v
        raise AssertionException("Can't find page version.")


def parse_pages_metadata(src: AbstractPath, uuid: str,
                         content_version: Literal[1, 2], content_raw: Dict) -> Iterator[RMPage]:
    if content_version == 1:
        if "pages" not in content_raw:
            raise MissingAttribute("pages", "content")
        if "redirectionPageMap" not in content_raw:
            raise MissingAttribute("redirectionPageMap", "content")
        for bg_pdf_page_idx, page_uuid in zip(content_raw["redirectionPageMap"], content_raw["pages"]):
            path = src.join(uuid, f"{page_uuid}.rm")
            if path.exists():
                yield RMPage(path, uuid, page_uuid, None, bg_pdf_page_idx, parse_page_version(path))
            else:
                yield RMPage(path, uuid, page_uuid, None, bg_pdf_page_idx, None)
    else:
        if "cPages" not in content_raw:
            raise MissingAttribute("cPages", "content")
        if "pages" not in content_raw["cPages"]:
            raise MissingAttribute("cPages.pages", "content")
        pages = content_raw["cPages"]["pages"]
        for page in pages:
            if "id" not in page:
                raise MissingAttribute("cPages.pages[].id", "content")
            page_uuid = page["id"]
            path = src.join(uuid, f"{page_uuid}.rm")
            template = page.get("template", {}).get("value", None)
            bg_pdf_page_idx = page.get("redir", {}).get("value", None)
            if path.exists():
                yield RMPage(path, uuid, page_uuid, template, bg_pdf_page_idx, parse_page_version(path))
            else:
                yield RMPage(path, uuid, page_uuid, template, bg_pdf_page_idx, None)


def parse_files_metadata(src: AbstractPath) -> Iterator[File]:
    uuid_list = list(set([ID_PATTERN.fullmatch(f.name()).group(1) for f in src.listdir()
                          if ID_PATTERN.fullmatch(f.name()) is not None]))
    for uuid in uuid_list:
        try:
            # if it's a tombstone or dirty file then there are no other available files
            if src.join(f"{uuid}.tombstone").exists() or src.join(f"{uuid}.dirty").exists():
                if any(src.join(f"{uuid}.{ext}").exists() for ext in KNOWN_FILE_EXTENSIONS + KNOWN_FOLDER_EXTENSIONS
                       if ext not in ["tombstone", "dirty", "RM_FOLDER"]) or src.join(uuid).exists():
                    raise AssertionException("tombstone or dirty file present along side other files.")
                continue

            # otherwise there should be a metadata and a content
            metadata = src.join(f"{uuid}.metadata")
            if not metadata.exists():
                raise AssertionException("The metadata file is missing.")

            # check for the relevant field in the metadata file
            with metadata.open() as f:
                metadata_raw = json.load(f)
                if "parent" not in metadata_raw:
                    raise MissingAttribute("parent", "metadata")
                parent_uuid = metadata_raw["parent"]
                if "type" not in metadata_raw:
                    raise MissingAttribute("type", "metadata")
                filetype = FileType(metadata_raw["type"])
                if filetype not in [FileType.DOCUMENT, FileType.COLLECTION]:
                    raise UnknownValue(filetype, 'type')
                if "visibleName" not in metadata_raw:
                    raise MissingAttribute("visibleName", "metadata")
                name = metadata_raw["visibleName"]

            if filetype == FileType.DOCUMENT:
                # there must be a content for document
                content = src.join(f"{uuid}.content")
                if not content.exists():
                    raise AssertionException("The content file is missing.")
                # find content version and parse page metadata
                with content.open() as f:
                    content_raw = json.load(f)
                    if "formatVersion" not in content_raw:
                        raise MissingAttribute("formatVersion", "content")
                    content_version = content_raw["formatVersion"]
                    if content_version not in [1, 2]:
                        raise UnknownValue(content_version, 'formatVersion')
                    pages = parse_pages_metadata(src, uuid, content_version, content_raw)
                # check for the background pdf
                bg_path = src.join(f"{uuid}.pdf")
                if not bg_path.exists():
                    bg_path = None
                yield File(uuid, name, filetype, parent_uuid, src, bg_path, list(pages))
            else:
                yield File(uuid, name, filetype, parent_uuid, src, None, None)
        except Exception as e:
            logger.error(f"Failed to parse {uuid}: {e}")


def list_files(src: AbstractPath) -> Dict[str, File]:
    files = {}
    for file in parse_files_metadata(src):
        files[file.uuid] = file
    return files

def get_filename(file: File) -> str:
    ext = ".pdf" if file.type == FileType.DOCUMENT else ""
    return f"{file.name}{ext}"

def get_fullpath(dst: Path, file: File, files: Dict[str, File]) -> Path:
    if file.parent_uuid == "":
        return dst.joinpath(get_filename(file))
    if file.parent_uuid == "trash":
        return dst.joinpath(f"_trash", get_filename(file))
    if file.parent_uuid not in files:
        logger.warning(f"Could not find parent '{file.parent_uuid}' for '{get_filename(file)}' ({file.uuid})")
        return dst.joinpath(get_filename(file))
    return get_fullpath(dst, files[file.parent_uuid], files).joinpath(get_filename(file))
