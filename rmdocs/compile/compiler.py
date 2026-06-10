import logging
from pathlib import Path
from typing import Optional, Any

from rmscene import SceneTree

from rmdocs.compile.param import CompilerParameters

logger = logging.getLogger(__name__)


class Compiler:

    def __init__(self, param: CompilerParameters):
        self.param = param

    def compile_tree(self, tree: SceneTree, include_template: Optional[Path] = None) -> Any:
        """
        Compile a rm file
        :param tree: The SceneTree parse from the rm file
        :param include_template: the path to the background template
        :return: The compiled file in appropriate format
        """
        raise NotImplementedError()
