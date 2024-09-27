from io import BytesIO
import os

import diskcache
from diskcache import Cache
import cairosvg.surface
from PIL import Image

from svglue import render_svg_string


cache = Cache(__name__)

__CACHE_DISABLED = os.environ.get("DECK_SVG_CACHE_DISABLED", 0)


def empty_svg_string():
    return "<svg></svg>"


def constant_svg(path):
    with open(path) as f:
        svg_data = f.read()
    pil = svg_string_to_pil(svg_data)
    return lambda _: pil


def _svgs_into_svg_string(txt, replacements):
    return get_or_compute(
        render_svg_string,
        src=txt,
        replacements=replacements,
    )


def interpolate_svg_to_string(
    filepath=None,
    string=None,
    literal_replacements=None,
    text_replacements=None,
    svg_replacements=None,
):
    literal_replacements = literal_replacements or {}
    text_replacements = text_replacements or {}
    svg_replacements = svg_replacements or {}

    if not filepath and not string:
        raise TypeError("Need to provide either 'filepath' or 'string'")

    if filepath and not string:
        with open(filepath, "r") as f:
            string = f.read()

    for (lit_src, lit_sub) in literal_replacements.items():
        string = string.replace(lit_src, lit_sub)

    text_interpolated_string = string.format(**text_replacements)
    return _svgs_into_svg_string(
        text_interpolated_string.encode("utf-8"),
        svg_replacements,
    )


def interpolate_svg(
    filepath=None,
    string=None,
    literal_replacements=None,
    text_replacements=None,
    svg_replacements=None,
):
    return svg_string_to_pil(
        interpolate_svg_to_string(
            filepath=filepath,
            string=string,
            literal_replacements=literal_replacements,
            text_replacements=text_replacements,
            svg_replacements=svg_replacements,
        )
    )


def svg_string_to_pil(svg):
    return get_or_compute(_svg_string_to_pil, svg)


def _svg_string_to_pil(svg):
    tree = cairosvg.surface.Tree(bytestring=svg.encode("utf-8"))
    f = BytesIO()
    cairosvg.surface.PNGSurface(tree, f, dpi=96).finish()
    return Image.open(f)


# -- This whole bit should just be @cache.memoize on the relevant functions,
# -- but unfortunately I need to break it out in case I have to debug cache
# -- misses.  This is mostly just a copy/paste of the wrapper from memoize()
# -- with simplifications thrown in for my use case.

ENOVAL = object()

def get_or_compute(func, *args, **kwargs):
    """Wrapper for callable to cache arguments and return values."""
    if __CACHE_DISABLED:
        return func(*args, **kwargs)

    base = (func.__name__,)
    key = diskcache.core.args_to_key(base, args, kwargs, False, [])
    result = cache.get(key, default=ENOVAL, retry=True)

    if result is ENOVAL:
        result = func(*args, **kwargs)
        # Save the result.  Expire it in one day
        cache.set(key, result, expire=3600*24, retry=True)

    return result
