import json
from typing import Optional, Union, Literal

from rmdocs.io import AbstractPath
from rmdocs.struct.content import Content, FileType


class Metadata:
    def __init__(self, src: AbstractPath, uuid: str):
        self.src = src
        self.uuid = uuid

        # read file
        f = src.join(uuid + ".metadata").open("r")
        self.raw = json.load(f)
        f.close()

    def get_parent_uuid(self) -> str:
        return self.raw["parent"]

    def get_name(self) -> str:
        return self.raw["visibleName"]

    def get_file_type(self) -> FileType:
        return self.raw["type"]

    def get_associated_content(self) -> Optional[Content]:
        return Content.from_file(self.src, self.uuid, self.get_file_type())

    def test_assertion(self, uuid_list: list[str]) -> Union[Literal[True], str]:
        # the metadata contains is type, visibleName and parent
        # - type is one of FileType valid type
        # - parent is in uuid
        if not all([p in self.raw for p in ["type", "visibleName", "parent"]]):
            return "Missing attributes in .metadata file."
        if not (self.raw["parent"] in uuid_list or self.raw["parent"] in ["", "trash"]):
            return "Can't find parent of this file."
        if not FileType.valid_type(self.raw["type"]):
            return "This document has an unknown type."
        return True
