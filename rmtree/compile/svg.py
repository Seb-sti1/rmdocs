"""
Convert blocks to svg file.

This file is under LGPL license (https://www.gnu.org/licenses/lgpl-3.0.en.html)

Code originally from https://github.com/lschwetlick/maxio (LGPL) through
https://github.com/chemag/maxio (LGPL) then used in https://github.com/ricklupton/rmc (MIT).
"""
import io
import logging
import string
from pathlib import Path
from typing import Optional, Dict, Tuple

from rmscene import SceneTree, CrdtId
from rmscene import scene_items as si
from rmscene.text import TextDocument

from rmtree.compile.brush import lookup_pen_color, Pen
from rmtree.compile.compiler import Compiler
from rmtree.compile.param import CompilerParameters

logger = logging.getLogger(__name__)


class SVG(Compiler):
    SVG_HEADER = string.Template("""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" height="$height" width="$width" viewBox="$viewbox">""")

    def __init__(self, param: CompilerParameters):
        super().__init__(param)

    def scale(self, screen_unit: float) -> float:
        return screen_unit * self.param.screen.scale

    def read_template_svg(self, template_path: Path) -> str:
        lines = template_path.read_text().splitlines()
        return "\n".join(lines[2:-2])

    def build_anchor_pos(self, txt: Optional[si.Text]) -> Dict[CrdtId, int]:
        """
        Find the anchor pos

        :param txt: the root text of the remarkable file
        """
        anchor_pos = {}

        if txt is not None:
            # Save anchor from text
            doc = TextDocument.from_scene_item(txt)
            ypos = txt.pos_y + self.param.text.text_top_y
            top_of_text = ypos
            for i, p in enumerate(doc.contents):
                anchor_pos[p.start_id] = ypos
                for subp in p.contents:
                    for k in subp.i:
                        anchor_pos[k] = ypos  # TODO check these anchor are used
                ypos += self.param.text.line_heights.get(p.style.value, 70)
            bottom_of_text = ypos

            # Special anchors: groups drawn at the top/bottom of the page,
            # not anchored to any specific paragraph.
            anchor_pos[CrdtId(0, 281474976710654)] = top_of_text
            anchor_pos[CrdtId(0, 281474976710655)] = bottom_of_text
        else:
            # No text: fall back to fixed positions at top/bottom of screen
            anchor_pos[CrdtId(0, 281474976710654)] = 0
            anchor_pos[CrdtId(0, 281474976710655)] = self.param.screen.screen_height

        return anchor_pos

    def get_anchor(self, item: si.Group, anchor_pos):
        anchor_x = 0.0
        anchor_y = 0.0
        if item.anchor_id is not None:
            assert item.anchor_origin_x is not None
            anchor_x = item.anchor_origin_x.value
            if item.anchor_id.value in anchor_pos:
                anchor_y = anchor_pos[item.anchor_id.value]
                logger.debug("Group anchor: %s -> y=%.1f (scalded y=%.1f)",
                             item.anchor_id.value,
                             anchor_y,
                             self.scale(anchor_y))
            else:
                logger.warning("Group anchor: %s is unknown!", item.anchor_id.value)

        return anchor_x, anchor_y

    def get_bounding_box(self, item: si.Group,
                         anchor_pos: Dict[CrdtId, int],
                         default: Tuple[int, int, int, int]) -> Tuple[float, float, float, float]:
        """
        Get the bounding box of the given item.
        The minimum size is the default size of the screen.

        :return: x_min, x_max, y_min, y_max: the bounding box in screen units (need to be scalded using xx and yy functions)
        """
        x_min, x_max, y_min, y_max = default

        for child_id in item.children:
            child = item.children[child_id]
            if isinstance(child, si.Group):
                anchor_x, anchor_y = self.get_anchor(child, anchor_pos)
                x_min_t, x_max_t, y_min_t, y_max_t = self.get_bounding_box(child, anchor_pos, (0, 0, 0, 0))
                x_min = min(x_min, x_min_t + anchor_x)
                x_max = max(x_max, x_max_t + anchor_x)
                y_min = min(y_min, y_min_t + anchor_y)
                y_max = max(y_max, y_max_t + anchor_y)
            elif isinstance(child, si.Line):
                x_min = min([x_min] + [p.x for p in child.points])
                x_max = max([x_max] + [p.x for p in child.points])
                y_min = min([y_min] + [p.y for p in child.points])
                y_max = max([y_max] + [p.y for p in child.points])

        return x_min, x_max, y_min, y_max

    def draw_group(self, item: si.Group, output, anchor_pos):
        anchor_x, anchor_y = self.get_anchor(item, anchor_pos)
        output.write(
            f'\t\t<g id="{item.node_id}" transform="translate({self.scale(anchor_x)}, {self.scale(anchor_y)})">\n')
        for child_id in item.children:
            child = item.children[child_id]
            logger.debug("Group child: %s %s", child_id, type(child))
            if logger.root.level == logging.DEBUG:
                output.write(f'\t\t<!-- child {child_id} {type(child)} -->\n')
            if isinstance(child, si.Group):
                self.draw_group(child, output, anchor_pos)
            elif isinstance(child, si.Line):
                self.draw_stroke(child, output)
        output.write(f'\t\t</g>\n')

    def draw_stroke(self, item: si.Line, output):
        # print debug infos
        if logger.root.level == logging.DEBUG:
            logger.debug("Writing line: %s", item)
            output.write(f'\t\t\t<!-- Stroke tool: {item.tool.name} '
                         f'color: {item.color.name} thickness_scale: {item.thickness_scale} -->\n')

        # initiate the pen
        pen_color = lookup_pen_color(item.color, item.color_rgba)
        pen = Pen.create(item.tool, pen_color, item.thickness_scale)

        last_xpos = -1.
        last_ypos = -1.
        last_segment_width = segment_width = 0
        # Iterate through the point to form a polyline
        for point_id, point in enumerate(item.points):
            # align the original position
            xpos = point.x
            ypos = point.y
            if point_id % pen.segment_length == 0:
                # if there was a previous segment, end it
                if last_xpos != -1.:
                    output.write('"/>\n')

                segment_color = pen.get_segment_color(point.speed, point.direction, point.width, point.pressure,
                                                      last_segment_width)
                segment_width = pen.get_segment_width(point.speed, point.direction, point.width, point.pressure,
                                                      last_segment_width)
                segment_opacity = pen.get_segment_opacity(point.speed, point.direction, point.width, point.pressure,
                                                          last_segment_width)
                # create the next segment of the stroke
                output.write('\t\t\t<polyline ')
                output.write(f'style="fill:none; stroke:{segment_color}; '
                             f'stroke-width:{self.scale(segment_width):.3f}; opacity:{segment_opacity}" ')
                output.write(f'stroke-linecap="{pen.stroke_linecap}" ')
                output.write('points="')
                if last_xpos != -1.:
                    # Join to previous segment
                    output.write(f'{self.scale(last_xpos):.3f},{self.scale(last_ypos):.3f} ')
            # store the last position
            last_xpos = xpos
            last_ypos = ypos
            last_segment_width = segment_width

            # add current point
            output.write(f'{self.scale(xpos):.3f},{self.scale(ypos):.3f} ')

        # end stroke
        output.write('" />\n')

    def draw_text(self, text: si.Text, output):
        output.write('\t\t<g class="root-text" style="display:inline">')

        # add some style to get readable text
        output.write('''
                <style>
                    text.heading {
                        font: 14pt serif;
                    }
                    text.bold {
                        font: 8pt sans-serif bold;
                    }
                    text, text.plain {
                        font: 7pt sans-serif;
                    }
                </style>
        ''')

        y_offset = self.param.text.text_top_y

        doc = TextDocument.from_scene_item(text)
        for p in doc.contents:
            y_offset += self.param.text.line_heights.get(p.style.value, 70)

            xpos = text.pos_x
            ypos = text.pos_y + y_offset
            cls = p.style.value.name.lower()
            if str(p):
                # TODO: this doesn't take into account the CrdtStr.properties (font-weight/font-style)
                if logger.root.level == logging.DEBUG:
                    output.write(f'\t\t\t<!-- Text line char_id: {p.start_id} -->\n')
                output.write(f'\t\t\t<text x="{self.scale(xpos)}" y="{self.scale(ypos)}"'
                             f' class="{cls}">{str(p).strip()}</text>\n')
        output.write('\t\t</g>\n')

    def compile_tree(self, tree: SceneTree, include_template: Optional[Path] = None) -> Tuple[str,
    float, float, float, float]:
        output = io.StringIO()

        # find the anchor pos for further use
        anchor_pos = self.build_anchor_pos(tree.root_text)
        logger.debug("anchor_pos: %s", anchor_pos)

        # find the extremum along x and y
        x_min, x_max, y_min, y_max = self.get_bounding_box(tree.root, anchor_pos,
                                                           (- self.param.screen.screen_width // 2,
                                                            self.param.screen.screen_width // 2,
                                                            0,
                                                            self.param.screen.screen_height))
        width_pt = self.scale(x_max - x_min + 1)
        height_pt = self.scale(y_max - y_min + 1)
        logger.debug("x_min, x_max, y_min, y_max: %.1f, %.1f, %.1f, %.1f ; scaled %.1f, %.1f, %.1f, %.1f",
                     x_min, x_max, y_min, y_max,
                     self.scale(x_min), self.scale(x_max), self.scale(y_min), self.scale(y_max))

        output.write(self.SVG_HEADER.substitute(width=width_pt,
                                                height=height_pt,
                                                viewbox=f"{self.scale(x_min)} {self.scale(y_min)}"
                                                        f" {width_pt} {height_pt}") + "\n")

        if include_template is not None:
            output.write(self.read_template_svg(include_template))
            output.write(f'\n\t<rect fill="url(#template)" x="{self.scale(x_min)}" y="{self.scale(y_min)}"'
                         f' width="{width_pt}" height="{height_pt}"/>\n')

        output.write(f'\t<g id="p1" style="display:inline">\n')

        if tree.root_text is not None:
            self.draw_text(tree.root_text, output)

        self.draw_group(tree.root, output, anchor_pos)

        # Closing page group
        output.write('\t</g>\n')
        # END notebook
        output.write('</svg>\n')

        return output.getvalue(), self.scale(x_min), self.scale(y_min), width_pt, height_pt
