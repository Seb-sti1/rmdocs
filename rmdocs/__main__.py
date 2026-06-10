import argparse
import logging
import zipfile
from pathlib import Path

from pypdf import PdfWriter
from tqdm import tqdm

from rmdocs.debug import ExportType, test_assertion
from rmdocs.io import LocalPath, ZipPath
from rmdocs.logger import setup_logging
from rmdocs.struct.file import list_files
from rmdocs.struct.page import PageRM

logger = logging.getLogger(__name__)


def main(args=None):
    parser = argparse.ArgumentParser("rmdocs", description="Process the file tree of the reMarkable tablet.")
    parser.add_argument("src", type=Path, help="The source file/folder.")
    parser.add_argument("dst", type=Path, nargs="?", help="The folder where the files are exported to."
                                                          "It defaults to the current folder for single file.")
    parser.add_argument("--debug", "-d", action="store_true", help="Set all loggers to DEBUG (including rmscene).")
    parser.add_argument("--test-compatibility", "-t", action="store_true",
                        help="Test if the files from the reMarkable are compatible with this program.")
    parser.add_argument("--ignore-assertion", "-ia", action="store_true",
                        help="Continue despite assertion errors. Output correctness is not guaranteed.")
    parser.add_argument("--ignore-compatibility", "-ic", action="store_true",
                        help="Continue despite compatibility errors. WARNING: the output will not be correct.")
    args = parser.parse_args(args)
    setup_logging(args.debug, args.test_compatibility)

    export_type = ExportType.UNKNOWN
    if args.src.is_file():
        if args.src.suffix == ".rm":
            export_type = ExportType.RM
        elif args.src.suffix == ".rmdoc":
            export_type = ExportType.RMDOC
    elif args.src.is_dir():
        if all(f.suffix == ".rm" for f in args.src.iterdir()):
            export_type = ExportType.RM_FOLDER
        elif all(f.suffix == ".rmdoc" for f in args.src.iterdir()):
            export_type = ExportType.RMDOC_FOLDER
        elif all(f.suffix != ".rmdoc" for f in args.src.iterdir()):
            export_type = ExportType.XOCHITL_FOLDER
    if export_type == ExportType.UNKNOWN:
        parser.error("Unknown extension or content.")
    if not args.dst and export_type not in [ExportType.RMDOC, ExportType.RM] and not args.test_compatibility:
        parser.error("Please specify the 'dst' argument.")

    dst = args.dst
    if not args.dst and export_type in [ExportType.RMDOC, ExportType.RM]:
        dst = Path.cwd()

    if export_type == ExportType.XOCHITL_FOLDER:
        is_compatible, are_assertions_correct = test_assertion(args.src)
    else:
        # FIXME make it easier to check assertion and compatibility
        is_compatible, are_assertions_correct = True, True

    if args.test_compatibility:
        exit(0)
    if not (is_compatible or args.ignore_compatibility) and not (are_assertions_correct or args.ignore_assertion):
        exit(-1)

    if export_type in [ExportType.XOCHITL_FOLDER, ]:
        files = list_files(LocalPath(args.src))
        progress = tqdm(files.items())
        for uuid, f in progress:
            progress.set_description(str(f))
            try:
                f.export(dst.joinpath(f.get_path(files)))
            except Exception as e:
                logger.error(f"Failed to export {f.get_name()}: {e}")
    elif export_type in [ExportType.RMDOC, ExportType.RMDOC_FOLDER]:
        for path in [args.src] if export_type == ExportType.RMDOC else args.src.iterdir():
            with zipfile.ZipFile(path) as zf:
                path = ZipPath(zf)
                files = list_files(path)
                progress = tqdm(files.items())
                for uuid, f in progress:
                    progress.set_description(str(f))
                    try:
                        f.export(dst)
                    except Exception as e:
                        logger.error(f"Failed to export {f.get_name()}: {e}")
    elif export_type in [ExportType.RM, ExportType.RM_FOLDER]:
        for path in [args.src] if export_type == ExportType.RM else args.src.iterdir():
            page = PageRM(LocalPath(path), "", "", {})
            svg_pdf, _ = page.export()
            output_pdf = PdfWriter()
            output_pdf.add_page(svg_pdf)
            output_pdf.write(dst.joinpath(path.stem + ".pdf"))
            output_pdf.close()


if __name__ == "__main__":
    main()
