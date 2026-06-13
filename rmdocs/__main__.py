import argparse
import logging
import zipfile
from pathlib import Path

from pypdf import PdfWriter
from tqdm import tqdm

from rmdocs.export import export, export_page, ExportType
from rmdocs.io import LocalPath, ZipPath
from rmdocs.logger import setup_logging
from rmdocs.parse import list_files, FileType, get_fullpath, parse_page_version, PageVersion, RMPage, get_filename

logger = logging.getLogger(__name__)


def main(args=None):
    parser = argparse.ArgumentParser("rmdocs", description="Process the file tree of the reMarkable tablet.")
    parser.add_argument("src", type=Path, help="The source file/folder.")
    parser.add_argument("dst", type=Path, nargs="?", help="The folder where the files are exported to. "
                                                           "Defaults to the current folder for single files.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Set all loggers to DEBUG.")
    parser.add_argument("--dry-run", action="store_true", help="Parse but do not export. Useful to test assertions.")
    args = parser.parse_args(args)
    setup_logging(args.verbose)

    # determine what type of input the user provided
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

    if not args.dst and export_type not in [ExportType.RMDOC, ExportType.RM] and not args.dry_run:
        parser.error("Please specify the 'dst' argument.")

    dst = args.dst or Path.cwd()

    if export_type == ExportType.XOCHITL_FOLDER:
        files = list_files(LocalPath(args.src))
        progress = tqdm(files.items())
        for uuid, f in progress:
            if f.type == FileType.COLLECTION:
                continue
            fullpath = get_fullpath(dst, f, files)
            progress.set_description(str(fullpath))
            try:
                export(fullpath, f)
            except Exception as e:
                logger.error(f"Failed to export {f.name}: {e}")
    elif export_type in [ExportType.RMDOC, ExportType.RMDOC_FOLDER]:
        for path in [args.src] if export_type == ExportType.RMDOC else args.src.iterdir():
            with zipfile.ZipFile(path) as zf:
                path = ZipPath(zf)
                files = list_files(path)
                progress = tqdm(files.items())
                for uuid, f in progress:
                    progress.set_description(str(f))
                    try:
                        export(dst.joinpath(get_filename(f)), f)
                    except Exception as e:
                        logger.error(f"Failed to export {f.name}: {e}")
    elif export_type in [ExportType.RM, ExportType.RM_FOLDER]:
        for path in [args.src] if export_type == ExportType.RM else args.src.iterdir():
            try:
                v = parse_page_version(LocalPath(path))
                if v != PageVersion.V6:
                    logger.error(f"'{path.name}' is version {v} which is incompatible. "
                                 f"Open the page, draw and remove a stroke to update it to v6.")
                    continue
                svg_pdf, _ = export_page(RMPage(LocalPath(path), "", "", None, -1, v))
                output_pdf = PdfWriter()
                output_pdf.add_page(svg_pdf)
                output_pdf.write(dst.joinpath(path.stem + ".pdf"))
                output_pdf.close()
            except Exception as e:
                logger.error(f"Failed to export {path.name}: {e}")


if __name__ == "__main__":
    main()
