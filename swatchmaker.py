#!/usr/bin/env python

"""Create swatches from a list of colors."""

from argparse import ArgumentParser
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Callable


FONT = 'font/Inconsolata-Bold.ttf'
CLEAR_BLACK = (0, 0, 0, 0)
Img = Image.Image
FilterDraw = Callable[[Img, int, Tuple[int, int, int, int]], Img]
EffectDraw = Callable[[Img], Img]


class Swatch:
    def new(size: Tuple[int, int], colors: List[str], rows=1) -> Callable:
        """Create new swatch group.

        This function returns a draw function that can
        be called to generate a PIL.Image.
        """
        if isinstance(colors, str):
            colors = [colors]
        error(rows > len(colors), 'More rows than avalailable colors.')
        colors = list(map(parse_rgba, colors))
        # Fit missing swatches in last row
        colors.extend([(0, 0, 0, 0)] * (len(colors) % rows))
        # Approximate image size if it is not divisible
        # into equal size rectangles
        col_per_row = len(colors) // rows
        width = int(round(size[0] / col_per_row) * col_per_row)
        height = int(round(size[1] / rows) * rows)
        master = Image.new('RGBA', (width, height))

        sw_width = int(width / col_per_row)
        sw_height = int(height / rows)

        def draw(filters: List[FilterDraw] = []) -> Img:
            """Draw swatches to a PIL.Image"""
            for y in range(rows):
                for x in range(col_per_row):
                    index = x + y * col_per_row
                    color = colors[index]
                    swatch = Image.new('RGBA', (sw_width, sw_height), color)
                    for f in filters:
                        if f and color[3] > 0:
                            swatch = f(swatch, index, color)
                    master.paste(swatch, (x * sw_width, y * sw_height))
            return master
        return draw

    def read_colors_file(filename: str) -> Tuple[List[str], List[str]]:
        """Read colors from a colors file

        Each line can define one color with an optional name preceding
        the color:

            1) f2f6f8
            2) 91, 128, 114
            4) orange: ef5350
            5) magenta = 252 158 182

        The color can be either in hex format without the leading '#'
        or RGB separated by commas or spaces.

        Inline comments denoted by a leading '#'.
        """
        colors, names = [], []
        with open(filename, 'r') as fp:
            for ln in fp:
                ln = ln.strip().split('#', 1)[0]
                if ln == '':
                    continue
                color = ln.replace('=', ':')
                if ':' in color:
                    name, color = color.split(':', 1)
                    names.append(name.strip())
                color = color.strip().replace(' ', ',')
                if ',' in color:
                    color = ','.join(filter(lambda x: x != '', color.split(',')))
                colors.append(color)
        return colors, names



class Filter:
    def empty() -> FilterDraw:
        def draw(im: Img, index: int, color: Tuple[int, int, int, int]) -> Img:
            return im
        return draw

    def shadow(height: int, blend: int) -> FilterDraw:
        if blend == 0:
            return Filter.empty()
        alpha = int(blend * 255)
        def draw(im: Img, index: int, color: Tuple[int, int, int, int]) -> Img:
            h = int(height * im.height)
            shadow = Image.new('RGBA', (im.width, h), (0, 0, 0, alpha))
            mask = Image.new('RGBA', (im.width, im.height), CLEAR_BLACK)
            mask.paste(shadow, (0, mask.height - h))
            return Image.alpha_composite(im, mask)
        return draw

    def label(size: int, offset=0) -> FilterDraw:
        fnt = ImageFont.truetype(FONT, size)
        def draw(im: Img, index: int, color: Tuple[int, int, int, int]) -> Img:
            offs = offset * im.height
            text = rgba_str(color)
            frame = Image.new('RGBA', im.size, CLEAR_BLACK)
            draw = ImageDraw.Draw(frame)
            height = im.height - (offs + size + 5)
            draw.text((5, height), text, font=fnt, fill=(0, 0, 0, 100))
            del draw
            return Image.alpha_composite(im, frame)
        return draw

    def name(names: List[str], size: int, pos=0, offset=0) -> FilterDraw:
        fnt = ImageFont.truetype(FONT, size)
        def draw(im: Img, index: int, color: Tuple[int, int, int, int]) -> Img:
            offs = offset * im.height
            if index >= len(names):
                return im
            text = names[index]
            frame = Image.new('RGBA', im.size, CLEAR_BLACK)
            tsize = fnt.getsize(text)

            if pos == 1:
                x = im.width // 2 - tsize[0] // 2
                y = im.height // 2 - tsize[1] // 2
            elif pos == 0:
                x, y = (10, 5 + tsize[1] // 2)

            draw = ImageDraw.Draw(frame)
            draw.text((x, y - offs // 2), text, font=fnt, fill=(0, 0, 0, 100))
            del draw
            return Image.alpha_composite(im, frame)
        return draw


class Effect:
    def border(border: int, color: str) -> EffectDraw:
        color = parse_rgba(color)
        def draw(im: Img) -> Img:
            size = (im.width + border * 2, im.height + border * 2)
            bg = Image.new('RGBA', size, color)
            frame = Image.new('RGBA', size, clear(color))
            frame.paste(im, (border, border))
            return Image.alpha_composite(bg, frame)
        return draw

    def title(text: str, size: int, color=None, border=0) -> EffectDraw:
        color = parse_rgba(color)
        def draw(im: Img) -> Img:
            height = im.height + border + size
            base = Image.new('RGBA', (im.width, height), clear(color))
            base.paste(im, (0, size + border))

            frame = Image.new('RGBA', base.size, clear(color))
            fnt = ImageFont.truetype(FONT, size)
            draw = ImageDraw.Draw(frame)
            draw.text((0, 0), text, font=fnt, fill=color)
            del draw
            return Image.alpha_composite(base, frame)
        return draw


def error(cond: bool, msg: str):
    if cond:
        print('error:', msg)
        exit(1)


def parse_size(size: str) -> Tuple[int, int]:
    return tuple(map(int, size.lower().split('x')))


def parse_rgba(color: str) -> Tuple[int, int, int, int]:
    if not color:
        return (0, 0, 0, 255)
    if ',' in color:
        # R,G,B,A format
        comp = [s.strip() for s in color.split(',')]
        comp.extend(['255'] * (4 % len(comp)))
        result = tuple(map(int, comp))
        error(len(result) < 4, 'Invalid color.')
        return result
    # hex format color
    color = color.strip('#')

    if len(color) == 3:
        comp = [x * 2 for x in color]
    else:
        comp = [color[i:i+2] for i in range(0, len(color), 2)]

    comp.extend(['ff'] * (4 % len(comp)))
    result = tuple(map(lambda c: int(c, 16), comp))
    error(len(result) < 4, 'Invalid color.')
    return result


def rgba_str(color: Tuple[int, int, int, int]) -> str:
    res = color[2]
    res |= color[1] << 8
    res |= color[0] << 16
    return '#{0:06x}'.format(res)


def clear(color: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    return (color[0], color[1], color[2], 0)


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    mut = parser.add_mutually_exclusive_group(required=True)

    parser.add_argument(
        'size',
        help='image width and height in pixels (ie 512x256)'
    )
    mut.add_argument(
        '--input', '-i',
        help='read colors from file'
    )
    mut.add_argument(
        '--colors', '-c',
        nargs='+',
        help='list of colors (use instead of --input)'
    )
    parser.add_argument(
        '--output', '-o',
        default='swatch.png',
        help='output file'
    )
    parser.add_argument(
        '--rows', '-r',
        help='split swatches in N rows',
        default=1,
        type=int
    )
    parser.add_argument(
        '--shadow', '-s',
        type=float,
        metavar=('SIZE', 'OPACITY'),
        help='shadow size and opacity (values between 0.0 and 1.0)',
        default=[0, 0],
        nargs=2
    )
    parser.add_argument(
        '--label', '-l',
        action='store_true',
        default=False,
        help='label colors with their hex value'
    )
    parser.add_argument(
        '--names', '-n',
        default=[],
        help='names for color swatches (leave empty if using file input)',
        nargs='*'
    )
    parser.add_argument(
        '--npos', '-p',
        type=int,
        default=0,
        help='position for color name (0: top-left, 1: middle)'
    )
    parser.add_argument(
        '--title', '-t',
        metavar=('TITLE', 'COLOR'),
        help='a title text and color',
        nargs=2
    )
    parser.add_argument(
        '--border', '-b',
        metavar=('SIZE', 'COLOR'),
        help='border size and color',
        nargs=2
    )
    parser.add_argument(
        '--fonts', '-f',
        type=int,
        metavar=('TITLE', 'NAME', 'LABEL'),
        help='font sizes (title [-t], name [-n], label [-l])',
        default=[24, 18, 16],
        nargs=3
    )

    argv = parser.parse_args()

    if argv.input:
        file = Swatch.read_colors_file(argv.input)
        argv.colors = file[0]
        if len(argv.names) == 0:
            argv.names = file[1]

    draw = Swatch.new(parse_size(argv.size), argv.colors, argv.rows)

    filters = [
        Filter.shadow(argv.shadow[0], argv.shadow[1]),
        Filter.label(argv.fonts[2], argv.shadow[0]) if argv.label else None,
        Filter.name(argv.names, argv.fonts[1], argv.npos, argv.shadow[0])
    ]
    im = draw(filters)

    if argv.title:
        border = int(argv.border[0]) if argv.border else 0
        im = Effect.title(
            text=argv.title[0],
            size=argv.fonts[0],
            color=argv.title[1],
            border=border)(im)

    if argv.border:
        im = Effect.border(int(argv.border[0]), argv.border[1])(im)

    im.save(argv.output)
