from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Dict, Tuple, Union, Literal

import cairosvg
from pypdf import PdfReader, PageObject
from rmscene import read_tree

import rmdocs.templates as templates
from rmdocs.compile.param import CompilerParameters
from rmdocs.compile.svg import SVG
from rmdocs.io import AbstractPath

logger = logging.getLogger(__name__)

RM_VERSION_HEADER = "reMarkable .lines file, version="


class PageVersion:
    V6 = 6
    V5 = 5
    V3 = 3

    VALID_VERSIONS: list[PageVersion] = [V6, V5, V3]


class Page:
    """
    Represents a page of a notebook
    """

    def __init__(self, path: AbstractPath, file_uuid: str, page_uuid: str, definition: Dict):
        self.path = path
        self.file_uuid = file_uuid
        self.page_uuid = page_uuid
        self.definition = definition

        self.template = None
        if "template" in definition:
            self.template = None if definition["template"]["value"] == "Blank" else definition["template"]["value"]

        self.bg_pdf_page_idx = None
        if "redir" in definition:
            self.bg_pdf_page_idx = definition["redir"]["value"]

    @staticmethod
    def from_file(src: AbstractPath, file_uuid: str, page_uuid: str, definition: Dict) -> Page:
        page_path = src.join(file_uuid, page_uuid + ".rm")
        if src.join(file_uuid, page_uuid + ".rm").exists():
            return PageRM(page_path, file_uuid, page_uuid, definition)
        else:
            return PageEmpty(page_path, file_uuid, page_uuid, definition)

    def get_page_uuid(self) -> str:
        return self.page_uuid

    def test_assertion(self) -> Union[Literal[True], str]:
        raise NotImplementedError("This is an abstract class")


class PageRM(Page):
    def __init__(self, path: AbstractPath, file_uuid: str, page_uuid: str, definition: Dict):
        super().__init__(path, file_uuid, page_uuid, definition)

        self.compiler_param = CompilerParameters()
        self.version = self.__compute_version__()

    def __compute_version__(self) -> PageVersion:
        headers = {v: RM_VERSION_HEADER + str(v) for v in PageVersion.VALID_VERSIONS}
        with self.path.open('rb') as f:
            file_header = f.read(max([len(headers[v]) for v in headers]))
            for v in headers:
                h = headers[v]
                if file_header.startswith(h.encode('ascii')):
                    return v

    def get_version(self) -> PageVersion:
        return self.version

    def export(self) -> Tuple[PageObject, Tuple[float, float, float, float]]:
        """
        Use rmc to convert a rm binary file to a svg and then to a pdf

        :return: A PageObject containing the drawing of the associated rm file
        """
        # find the template
        template = Path(os.path.join(Path(templates.__file__).parent, self.template + ".svg")) \
            if self.template is not None else None
        if template is not None and not template.exists():
            logger.warning(f"Can't find the specified template file ({template.name})")
            template = None

        # convert the rm file to svg
        compiler = SVG(self.compiler_param)
        with self.path.open('rb') as f:
            tree = read_tree(f)
            svg, x_shift, y_shift, w, h = compiler.compile_tree(tree, template)

        # convert the svg to a PDF without writing to the disk
        # use dpi=72 so that the PDF has the same resolution as the svg
        svg_pdf_data = cairosvg.svg2pdf(bytestring=svg.encode('utf-8'), dpi=72)
        svg_pdf_buffer = io.BytesIO(svg_pdf_data)
        svg_pdf = PdfReader(svg_pdf_buffer)
        assert len(svg_pdf.pages) == 1

        return svg_pdf.pages[0], (x_shift, y_shift, w, h)

    def test_assertion(self) -> Union[Literal[True], str]:
        if self.version != PageVersion.V6:
            return "This software is only compatible with rm file version 6."
        return True


class PageEmpty(Page):
    def __init__(self, path: AbstractPath, file_uuid: str, page_uuid: str, definition: Dict):
        super().__init__(path, file_uuid, page_uuid, definition)

    def test_assertion(self) -> Union[Literal[True], str]:
        return True
