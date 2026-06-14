import argparse
import logging
import zipfile
from pathlib import Path

from pypdf import PdfWriter
from rich.logging import RichHandler
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn, TimeRemainingColumn, TimeElapsedColumn, \
    TaskID

from rmdocs.export import export, export_page, ExportType
from rmdocs.io import LocalPath, ZipPath, AbstractPath
from rmdocs.parse import list_files, FileType, get_fullpath, parse_page_version, PageVersion, RMPage, get_filename

logger = logging.getLogger(__name__)


def export_collection(src: AbstractPath, dst: Path, is_xochitl: bool, dry_run: bool, progress: Progress, task: TaskID):
    files = list_files(src)
    documents = {uuid: f for uuid, f in files.items() if f.type != FileType.COLLECTION}
    if is_xochitl:
        progress.update(task, total=len(documents))
    for uuid, f in documents.items():
        fullpath = get_fullpath(dst, f, files) if is_xochitl else dst.joinpath(get_filename(f))
        progress.update(task, description=get_filename(f))
        if not dry_run:
            try:
                export(fullpath, f)
            except Exception as e:
                logger.error(f"Failed to export {f.name}: {e}")
        progress.advance(task)


def main(args=None):
    parser = argparse.ArgumentParser("rmdocs", description="Process the file tree of the reMarkable tablet.")
    parser.add_argument("src", type=Path, help="The source file/folder.")
    parser.add_argument("dst", type=Path, nargs="?", help="The folder where the files are exported to. "
                                                          "Defaults to the current folder for single files.")
    parser.add_argument("--verbose", "-v", action="count", default=0, help="Verbosity level.")
    parser.add_argument("--dry-run", action="store_true", help="Parse but do not export. Useful to test assertions.")
    args = parser.parse_args(args)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        handlers=[RichHandler(rich_tracebacks=True)])
    logging.getLogger("rmdocs").setLevel({0: logging.INFO, 1: logging.INFO}.get(args.verbose, logging.DEBUG))
    logging.getLogger("rmscene").setLevel(
        {0: logging.CRITICAL, 1: logging.WARNING, 2: logging.INFO}.get(args.verbose, logging.DEBUG))

    export_type = ExportType.UNKNOWN
    if args.src.is_file():
        if args.src.suffix == ".rm":
            export_type = ExportType.RM
        elif args.src.suffix == ".rmdoc":
            export_type = ExportType.RMDOC
    elif args.src.is_dir():
        if all(f.suffix == ".rm" or f.name.endswith("-metadata.json") for f in args.src.iterdir()):
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
        with Progress(TextColumn("{task.description}"), BarColumn(),
                      MofNCompleteColumn(), TimeElapsedColumn(), TimeRemainingColumn()) as progress:
            task = progress.add_task("Exporting...", total=120)
            export_collection(LocalPath(args.src), dst, True, args.dry_run, progress, task)
    elif export_type in [ExportType.RMDOC, ExportType.RMDOC_FOLDER]:
        paths = [args.src] if export_type == ExportType.RMDOC else list(args.src.iterdir())
        with Progress(TextColumn("{task.description}"), BarColumn(),
                      MofNCompleteColumn(), TimeElapsedColumn(), TimeRemainingColumn()) as progress:
            # usually 1 doc per rmdoc
            task = progress.add_task("Exporting...", total=len(paths))
            for path in paths:
                with zipfile.ZipFile(path) as zf:
                    export_collection(ZipPath(zf), dst, False, args.dry_run, progress, task)
    elif export_type in [ExportType.RM, ExportType.RM_FOLDER]:
        paths = [args.src] if export_type == ExportType.RM \
            else [path for path in args.src.iterdir() if path.suffix == ".rm"]
        with Progress(TextColumn("{task.description}"), BarColumn(),
                      MofNCompleteColumn(), TimeElapsedColumn(), TimeRemainingColumn()) as progress:
            task = progress.add_task("Exporting...", total=len(paths))
            for path in paths:
                progress.update(task, description=path.name)
                try:
                    v = parse_page_version(LocalPath(path))
                    if v != PageVersion.V6:
                        logger.error(f"'{path.name}' is version {v} which is incompatible. "
                                     f"Open the page, draw and remove a stroke to update it to v6.")
                    else:
                        svg_pdf, _ = export_page(RMPage(LocalPath(path), "", "", None, -1, v))
                        output_pdf = PdfWriter()
                        output_pdf.add_page(svg_pdf)
                        output_pdf.write(dst / (path.stem + ".pdf"))
                        output_pdf.close()
                except Exception as e:
                    logger.error(f"Failed to export {path.name}: {e}")
                progress.advance(task)


if __name__ == "__main__":
    main()
