from dataclasses import dataclass, field
from typing import Dict

from rmscene import scene_items as si


@dataclass
class ScreenParameters:
    screen_width: int = 1404
    screen_height: int = 1872
    screen_dpi: int = 226
    scale: float = field(init=False)
    page_width_pt: float = field(init=False)
    page_height_pt: float = field(init=False)

    def __post_init__(self):
        self.scale = 72.0 / self.screen_dpi
        self.page_width_pt = self.screen_width * self.scale
        self.page_height_pt = self.screen_height * self.scale


@dataclass
class BrushParameters:
    pass


@dataclass
class TextParameters:
    text_top_y: int = -88
    line_heights: Dict[si.ParagraphStyle, int] = field(default_factory=lambda: {
        si.ParagraphStyle.PLAIN: 70,
        si.ParagraphStyle.BULLET: 35,
        si.ParagraphStyle.BULLET2: 35,
        si.ParagraphStyle.BOLD: 70,
        si.ParagraphStyle.HEADING: 150,
        si.ParagraphStyle.CHECKBOX: 35,
        si.ParagraphStyle.CHECKBOX_CHECKED: 35,
    })


@dataclass
class CompilerParameters:
    screen: ScreenParameters = field(default_factory=ScreenParameters)
    brush: BrushParameters = field(default_factory=BrushParameters)
    text: TextParameters = field(default_factory=TextParameters)