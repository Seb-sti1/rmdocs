import io
import logging
import os
import traceback
from enum import Enum, auto
from pathlib import Path
from typing import Tuple

import cairosvg
from pypdf import PdfReader, PageObject, PdfWriter, Transformation
from pypdf.annotations import FreeText
from rmscene import read_tree

from rmdocs.assertion import AssertionException
from rmdocs.compile.param import CompilerParameters
from rmdocs.compile.svg import SVG
from rmdocs.parse import RMPage, File, PageVersion, FileType

logger = logging.getLogger(__name__)


class ExportType(Enum):
    UNKNOWN = auto()
    RM = auto()
    RMDOC = auto()
    RM_FOLDER = auto()
    RMDOC_FOLDER = auto()
    XOCHITL_FOLDER = auto()


def replace_invalid_char(string: str) -> str:
    for char in ["/", ":", "*", "?", "\"", "<", ">", "|"]:
        string = string.replace(char, "")
    return string


def export_page(page: RMPage, compiler_param: CompilerParameters = CompilerParameters()) -> Tuple[
    PageObject, Tuple[float, float, float, float]]:
    """
    Use compile to convert a rm binary file to a svg and then to a PDF

    :return: A PageObject containing the drawing of the associated rm file
    """
    # TODO redo template from scratch

    # convert the rm file to svg
    compiler = SVG(compiler_param)
    with page.path.open('rb') as f:
        tree = read_tree(f)
        svg, x_shift, y_shift, w, h = compiler.compile_tree(tree, None)

    # convert the svg to a PDF without writing to the disk
    # use dpi=72 so that the PDF has the same resolution as the svg
    svg_pdf_data = cairosvg.svg2pdf(bytestring=svg.encode('utf-8'), dpi=72)
    svg_pdf_buffer = io.BytesIO(svg_pdf_data)
    svg_pdf = PdfReader(svg_pdf_buffer)
    assert len(svg_pdf.pages) == 1

    return svg_pdf.pages[0], (x_shift, y_shift, w, h)


def __add_annotation__(doc: PdfWriter, page_number: int, content: str,
                       width=400, height=40) -> None:
    annotation = FreeText(
        text=content,
        rect=(0, 0, width, height),
        font="Arial",
        italic=True,
        font_size="20pt",
        font_color="ffffff",
        border_color=None,
        background_color=None,
    )
    annotation.flags = 4
    doc.add_annotation(page_number=page_number, annotation=annotation)


def export(fullpath: Path, file: File, compiler_param: CompilerParameters = CompilerParameters()):
    if file.type == FileType.COLLECTION:
        logger.critical(f"{file.uuid} is a collected. Nothing to do.")
        return
    pages = file.pages
    if pages is None:
        raise AssertionException("Notebooks must have pages.")

    background_pdf_path = file.bg_path

    # create the folder tree (if needed)
    os.makedirs(str(fullpath.parent), exist_ok=True)

    if all([page is None for page in pages]):
        if background_pdf_path is not None:
            background_pdf_path.copy(str(fullpath))
        else:
            logger.critical(f"{fullpath} is empty... It will not be exported to disk.")
    else:
        bg_pdf = PdfReader(background_pdf_path.open('rb')) if background_pdf_path is not None else None
        output_pdf = PdfWriter()
        for i in range(max(len(pages), 0 if bg_pdf is None else len(bg_pdf.pages))):
            # find rm page and associated background pdf page
            page = None
            background_page = None
            if i < len(pages):
                p = pages[i]
                if p.version is not None:
                    page = p
                if bg_pdf is not None and p.bg_pdf_page_idx is not None:
                    background_page = bg_pdf.pages[p.bg_pdf_page_idx]
            else:
                # this can only happen for files using content v1
                if bg_pdf is not None:
                    background_page = bg_pdf.pages[i]

            if page is not None and page.version == PageVersion.V6:
                try:
                    # get the svg as a pdf
                    svg_pdf_p, (x_shift, y_shift, w_svg, h_svg) = export_page(page, compiler_param)
                    # get size of the background_page
                    w_bg = 0 if background_page is None else background_page.cropbox.width
                    h_bg = 0 if background_page is None else background_page.cropbox.height
                    # add a blank page that can contains both svg and background pdf
                    width, height = max(w_svg, w_bg), max(h_svg, h_bg)
                    new_page = output_pdf.add_blank_page(width, height)
                    # compute position of svg and background in the new_page
                    x_svg, y_svg = 0, 0
                    x_bg, y_bg = 0, 0
                    if w_svg > w_bg:
                        x_bg = width / 2 - w_bg / 2 - (w_svg / 2 + x_shift)
                    elif w_svg < w_bg:
                        x_svg = width / 2 - w_svg / 2 + (w_svg / 2 + x_shift)
                    if h_svg > h_bg:
                        y_bg = height - h_bg + y_shift
                    elif h_svg < h_bg:
                        y_svg = height - h_svg - y_shift
                    # merge background_page and svg_pdf_p
                    if background_page is not None:
                        new_page.merge_transformed_page(background_page,
                                                        Transformation().translate(x_bg, y_bg))
                    new_page.merge_transformed_page(svg_pdf_p,
                                                    Transformation().translate(x_svg, y_svg))
                except Exception:
                    output_pdf.add_blank_page(400, 500)
                    __add_annotation__(output_pdf,
                                       len(output_pdf.pages) - 1,
                                       f"An error occurred while exporting this page.\n\n\n"
                                       f"{traceback.format_exc()}",
                                       400,
                                       500)
                    logger.warning(f"Failed to export page {page.page_uuid} of {page.file_uuid}:")
                    traceback.print_exc()
            else:
                if background_page is not None:
                    output_pdf.add_page(background_page)
                else:
                    output_pdf.add_blank_page(400, 500)
                if page is not None:  # if there is a non v6 page
                    __add_annotation__(output_pdf,
                                       len(output_pdf.pages) - 1,
                                       f"This page uses a rm v{page.version}."
                                       f" It is incompatible with this software.\n"
                                       f"Please go to this page, draw and remove a stroke in order"
                                       f" to update the page to v6.")
        if len(output_pdf.pages) > 0:
            output_pdf.write(fullpath)
            output_pdf.close()
        else:
            logger.critical(f"{fullpath} is empty... It will not be exported to disk.")
