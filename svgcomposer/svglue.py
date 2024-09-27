#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Forked then very heavily modified from
# https://raw.githubusercontent.com/mbr/svglue/master/svglue/__init__.py
#
# Copyright (c) 2016 Marc Brinkmann
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from base64 import b64encode
from uuid import uuid4

from lxml import etree

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
RECT_TAG = "{http://www.w3.org/2000/svg}rect"
USE_TAG = "{http://www.w3.org/2000/svg}use"
HREF_ATTR = "{http://www.w3.org/1999/xlink}href"


class TemplateParseError(Exception):
    pass


class Template(object):
    @classmethod
    def load(cls, src=None, file=None):
        if src:
            return cls(etree.fromstring(src))
        else:
            return cls(etree.parse(file))

    @classmethod
    def render_svg_string(
        cls,
        src=None,
        file=None,
        replacements=None,
        clean_layout_elements=True,
    ):
        replacements = replacements or {}
        tpl = cls.load(src=src, file=file)
        for (tid, svg_string) in replacements.items():
            tpl.replace_rect_with_svg_string(tid, svg_string)
        if clean_layout_elements:
            tpl.expunge_layout_elements()
        return tpl.tostring()

    def __init__(self, doc):
        self._doc = doc
        self._tid_cache = {}
        self._defs = None

    def get_by_id(self, tid):
        if tid not in self._tid_cache:
            matches = self._doc.xpath(f"//*[@id='{tid}']")
            if len(matches) == 1:
                self._tid_cache[tid] = matches[0]
            else:
                raise LookupError(
                    f"Expected unique match for {tid}, instead got {matches}"
                )
        return self._tid_cache[tid]

    def get_defs(self):
        if self._defs is None:
            defs = self._doc.xpath(
                "/svg:svg/svg:defs",
                namespaces={"svg": SVG_NS},
            )

            if defs:
                self._defs = defs[0]
            else:
                self._defs = self._doc.getroot().insert(
                    0, etree.Element(f"{{{SVG_NS}}}defs")
                )
        return self._defs

    def replace_rect_with_svg_string(self, tid, svg):
        return self.replace_rect_with_svg_bytes(tid, svg.encode("utf-8"))

    def replace_rect_with_svg_bytes(self, tid, svg_bytes):
        return self.replace_rect_with_etree(tid, etree.fromstring(svg_bytes))

    def replace_rect_with_etree(self, tid, tree):
        # Get the rectangle we want to replace
        elem = self.get_by_id(tid)

        # Define an SVG fragment from the provided SVG XML tree
        doc_id = str(uuid4())
        tree.set('id', doc_id)
        # n.b., we need to set the height and width on the SVG here in the
        # import definition; heights and widths set on or around the `use`
        # itself will not apply
        tree.set('height', elem.attrib['height'])
        tree.set('width', elem.attrib['width'])
        self.get_defs().append(tree)

        # Mutate the rectangle from a `rect` to a `use` of the defined SVG
        # fragment.
        elem.tag = USE_TAG

        # Give it a new id in case we want to nest templates with duplicate ids
        new_id = str(uuid4())
        elem.set('id', new_id)

        ALLOWED_ATTRS = ('x', 'y')
        for attr in elem.attrib.keys():
            if not attr in ALLOWED_ATTRS:
                del elem.attrib[attr]

        elem.set(HREF_ATTR, '#' + doc_id)

        return self

    def expunge_layout_elements(self):
        layout_elements = self._doc.xpath(
            "//*[@inkscape:label='layout']",
            namespaces={"inkscape": INKSCAPE_NS},
        )
        parent_map = {elem: elem.getparent() for elem in layout_elements}
        for elem in layout_elements:
            parent_map[elem].remove(elem)

        return self

    def tostring(self):
        return etree.tostring(self._doc, encoding=str)

    def __str__(self):
        return self.tostring()


load = Template.load
render_svg_string = Template.render_svg_string
