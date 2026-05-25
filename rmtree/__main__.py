import argparse
import logging
from pathlib import Path

from tqdm import tqdm

from rmtree.debug import test_assertion
from rmtree.logger import setup_logging
from rmtree.struct.file import list_files

logger = logging.getLogger(__name__)


def main(args=None):
    parser = argparse.ArgumentParser("rmtree", description="Process the file tree of the reMarkable tablet.")
    parser.add_argument("src", type=Path, help="The source folder.")
    parser.add_argument("dst", type=Path, nargs="?", help="The folder where the files are exported to.")
    parser.add_argument("--debug", "-d", action="store_true", help="Set all loggers to DEBUG (including rmscene).")
    parser.add_argument("--test-compatibility", "-t", action="store_true",
                        help="Test if the files from the reMarkable are compatible with this program.")
    parser.add_argument("--ignore-assertion", "-ia", action="store_true",
                        help="Continue despite assertion errors. Output correctness is not guaranteed.")
    parser.add_argument("--ignore-compatibility", "-ic", action="store_true",
                        help="Continue despite compatibility errors. WARNING: the output will not be correct.")
    args = parser.parse_args(args)

    if not (args.dst or args.test_compatibility):
        parser.error("Please specify the 'dst' argument.")

    setup_logging(args.debug, args.test_compatibility)
    is_compatible, are_assertions_correct = test_assertion(args.src)

    if ((not args.test_compatibility)
            and (are_assertions_correct or args.ignore_assertion)
            and is_compatible or args.ignore_compatibility):
        # export all the files
        files = list_files(args.src)
        progress = tqdm(files.items())
        for uuid, f in progress:
            progress.set_description(str(f))
            try:
                f.export(args.dst.joinpath(f.get_path(files)))
            except Exception as e:
                logger.error(f"Failed to export {f.get_name()}: {e}")


if __name__ == "__main__":
    main()
