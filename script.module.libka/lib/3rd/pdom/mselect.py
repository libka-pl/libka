# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function

from collections import defaultdict

from .base import _make_html_list
from .base import base_str, PY2
from .base import Result, ResultParam, MissingAttr
from .base import pats
from .msearch import dom_search

from .selectorparser import parse as parse_selector
from .selectorparser import Selector, SetSelector, OrderedSetSelector, GroupSelector


# -------  DOM Select -------


class SetSelPartData:
    def __init__(self, res):
        self.nth = 1
        if PY2:
            self.res = res
        else:
            self.res = list(res)

    def __repr__(self):
        return 'Part({nth}, {res!r})'.format(nth=self.nth, res=self.res)


def _select_desc(res, html, selectors_desc, sync=False, flat=True):
    r"""
    Select descending tags "A B". Supports aternatives "{A, B}".

    Parameters
    res : list of str
        Result list, where found tags are appended.
    html : list of str
        List of input HTML parts.
    selectors_desc : list of str
        List of descending selectors. Each item can be aternativr list.
    sync : boll or Result.RemoveItem, default False
        if not False run dp,search in sync mode (returns None if not match).
    """
    part, tree, out_stack = html, None, []
    # Go through descending selector
    # print('=======  SINGLE LIST', selectors_desc.__class__.__name__, selectors_desc)
    for single_selector in selectors_desc:
        # print('=======  SINGLE', single_selector.__class__.__name__, single_selector)
        if isinstance(single_selector, list):
            assert isinstance(single_selector, SetSelector)
            # subgroup of set nodes: " { A, B, ...} "
            subhtml = list(part if tree is None else tree)
            subpart = [part] if tree else []
            # Ordered group: "{ SEL [, SEL]... }"
            if isinstance(single_selector, OrderedSetSelector):
                used = {}
                for sel in single_selector:
                    selhash = hash(sel)
                    # print('SEL-SET', sel, hash(sel), selhash in used, used)
                    if selhash in used:
                        res2 = used[selhash]
                        res2.nth += 1  # auto nth
                    else:
                        # res2 = []
                        # _select_desc(res2, subhtml, sel, sync=True, flat=flat)
                        res2 = [_select_desc([], sub2html, sel, sync=True, flat=flat) for sub2html in subhtml]
                        res2 = SetSelPartData(zip(*res2))  # nth, res2
                        # print('mix!!! SH', subhtml)
                        # print('mix!!! SR', res2)
                        used[selhash] = res2
                    # print('mix!!! sh', subhtml)
                    # print('mix!!! sr', res2)

                    look = sel[-1] if isinstance(sel, list) and sel else sel
                    nth = look.nth if isinstance(look, Selector) and look.nth else res2.nth
                    res2.nth = nth
                    if not res2:
                        return []
                    try:
                        res2 = res2.res[nth - 1]
                    except IndexError:
                        return []
                    # print('mix!!! sr0', res2)
                    subpart.append(res2)
                    # print('mix!!! sbP', subpart)
            else:
                # non-ordered set selector, always find first
                for sel in single_selector:
                    # print('SEL-SET', sel)
                    res2 = []
                    _select_desc(res2, subhtml, sel, sync=True, flat=flat)
                    # print('mix!!! sh', subhtml)
                    # print('mix!!! sr', res2)
                    if not res2:
                        return []
                    subpart.append(res2)
            # print('---')
            # print('Mix!!! P', part)
            # print('MIX!!! S', subpart)
            # append columns as rows
            if flat:
                # flat: all values in {...} are in flat list for each occurrence
                part = [[v for s in p for v in (s if type(s) is list else (s,))]
                        for p in zip(*subpart) if Result.RemoveItem not in p]

            else:
                part = [p for p in zip(*subpart) if Result.RemoveItem not in p]
            # print('MIX!!! P', part)
            continue
        # single node selector
        # print('--- SINGLE', single_selector)
        assert isinstance(single_selector, Selector)
        sel = single_selector
        tree_last = False
        tag = '' if sel.tag == '*' else sel.tag
        # node id, class, attribute selectors or pseudoclasses (what to return)
        rsync = False if not sync else True if sel.optional else Result.RemoveItem
        nodefilter = (lambda n: all(f(n) for f in sel.nodefilterlist)) if sel.nodefilterlist else None
        if sel.result:
            # print(f'dom_search({part if tree is None else tree!r}, tag={tag!r}, ret={dict(attrs)},'
            #       f' sync={rsync}, separate=True)')
            part, tree = dom_search(part if tree is None else tree, tag, attrs=dict(sel.attrs),
                                    ret=ResultParam(sel.result, missing=MissingAttr.NoSkip,
                                                    separate=True, sync=rsync, flat=flat, nodefilter=nodefilter,
                                                    position=sel.elem_pos, source=sel.item_source))
            if not tree:
                # print('PART', part, 'RETURN.')
                # print('TREE', tree, 'RETURN!')
                return []
            if part and not sel.optional:
                for i, v in enumerate(part):
                    if v == [Result.RemoveItem]:
                        part[i] = Result.RemoveItem
            if sel.result == [Result.NoResult]:
                part = None
            else:
                out_stack.append(part)
            tree_last = True
            # print('PART', list(zip(part, tree)))
            # res += list(zip(res, part))
        else:
            # print(f'dom_search({part if tree is None else tree!r}, tag={tag!r}, attrs={dict(sel.attrs)}, sync={rsync})')
            part, tree = dom_search(part if tree is None else tree, tag, attrs=dict(sel.attrs),
                                    ret=ResultParam(Result.Node, sync=rsync, flat=flat, nodefilter=nodefilter,
                                                    position=sel.elem_pos, source=sel.item_source)), None
            if not part:
                # print('PART', part, 'RETURN!')
                # print('TREE', tree, 'RETURN.')
                return []
        # print('PART', part)
        # print('TREE', tree)
        # print('STACK', out_stack)
    # print('SelPART', part)
    # print('SelSTACK.1', out_stack)
    if part is None or len(out_stack) > 1 or (out_stack and not tree_last):
        if tree is None and part:
            out_stack.append(part)
        # print('SelSTACK.2', out_stack)
        # print('SelSTACK.3', list(zip(*out_stack)))
        res += list(zip(*out_stack))
    else:
        res += part
    # print(f'dom_select() retutns: {res!r}')  # XXX
    return res


def _select_group(res, html, group_selector, flat=True):
    # Go through set selector
    assert isinstance(group_selector, GroupSelector)
    for sel in group_selector:
        # print('SEL-SET', sel)
        _select_desc(res, html, sel, flat=flat)


def dom_select(html, selectors, flat=None):
    r"""
    Find data in HTML by CSS / jQuery simplified selector.

    Parameters
    ----------
    html : str or bytes or Node or DomMatch or list of str or list of bytes or list of Node
        HTML/XML source. Directly or list of HTML/XML parts.
    selectors : str or list of str
        Selector (or list of selectors).

    See CSS and jQuery selectors for base knowlage. This function support
    only a few selectors plus some extra extension.

    Supported selectors:
        - '*'          All elements
        - #id          The element with id
        - .class       All elements with class
        - tag          All <tag> elements
        - E1, E1       Or, all E1 and all E2 matched elements
        - E1 E2        Parent descendant, all E2 elements that are descendants of a E1 element
        - [attr]       All elements with a attribute `attr`
        - [attr=val]   All elements with a attribute value equal `val`
        - [attr^=val]  All elements with a attribute value starting with `val`
        - [attr$=val]  All elements with a attribute value ending with `val`
        - [attr~=val]  All elements with a attribute value containing word `val`
        - [attr|=val]  All elements with a attribute value containing word starting with`val`
        - [attr*=val]  All elements with a attribute value containing `val`

    Extra selectors:
        - { E1, E2 }   Set, E1 and E2 elements. All items must exist.
                       If extra options (?) is used and some item
                       doesn't exists None is returned.

    Pseudo elements are used to choise result:
        ::node      Returns Node(), it's default on last node
        ::content   Returns node content, e.g. 'A<b>B</b>'
        ::text      Returns note text (without tags), e.g. 'AB'
        ::attr(A)   Returns attribute `A`, comma separated list can be used
        (A)         Shortcut for ::attr(A)
        ::none      Do not return anything, but node has to exist
        ::DomMatch  Returns DomMatch nodes, for backward compability

    Examples
    --------

    >>> dom_select('<a>A</a>', 'a')
    [Node('A')]
    >>> dom_select('<a>A</a>', 'a::text')
    ['A']

    >>> dom_select('<a><b>Ba</b></a><z><b>Bz</b></z>', 'a b')
    [Node('Ba')]

    >>> dom_select('<a><b>B</b></a>', 'a { b, c? }')
    [(Node('Ba'), None)]
    >>> for b, c in dom_select('<a><b>B</b></a>', 'a { b, c? }'):
    >>>     print(b.text, 'no C' if c is None else c.text)

    >>> dom_select('<a x="1">A</a>', 'a(x)')
    [['1']]

    """
    # TODO   Selectors:
    # TODO   - [attribute!=value]
    # TODO   - A > B
    # TODO   - A + B
    # TODO   - fist, last, nth, etc.
    #
    # print(' --- search for "{}"'.format(selectors))
    if flat is None:
        flat = dom_select.flat
    ret = []
    if isinstance(selectors, base_str):
        ret = None
        selectors = [selectors]

    html = _make_html_list(html)

    # all selector from list
    for selgrp in selectors:
        selgrp = parse_selector(selgrp)
        # Go through set selector
        res = []  # All matches for single selector
        _select_group(res, html, selgrp, flat=flat)
        # print('RES', res)
        if ret is None:
            ret = res
        else:
            ret.append(res)
    return ret


# Default behavior.
dom_select.flat = True


if __name__ == '__main__':

    # DEBUG only, Do NOT use it

    def printres(*args):
        print('\033[33;1m>\033[0m', *args, sep=' \033[33m|\033[0m ', end=' \033[33m|\033[0m\n')

    if 0:
        html = '<a x="11" y="12">A1<b>B1</b><c>C1</c></a> <a x="21" y="22">A2<b>B2</b><cc/></a>'

        for (a,), b, c in dom_select(html, 'a::node {b, c?}'):
            print(a.text, b.text, c and c.text)
        print('-')
        for row in dom_select(html, ':has(b)'):
            printres(row)
        print('-')
        for row in dom_select('<a x="1">A</a>', '[x]'):
            printres(row)

    if 0:
        # html = '<a><b>B1</b><c>C1</c><b>B2</b></a>'
        html = '<a><b>B1</b><c>C1</c><b>B2</b></a> <a><b>B21</b><c>C21</c><b>B22</b></a>'
        for row in dom_select(html, 'a {b, b, c}'):
            printres(row)

    if 0:
        for row in dom_select('<a>A1<c>C1</c>A2</a>X<b>B1<c>C2</c>B2</b>', '{a,b} c'):
            printres(row)

    if 0:
        # for row in dom_select('<a>A1</a><a>A2</a><a>A3</a><b>B1</b><b>B2</b>', '{a:2,a:1,a,a,b:2}'):
        for row in dom_select('<a><b>B1</b><c>C1</c><b>B2</b><c>C2</c></a>', '{a b:2, a c:2, a c:1}'):
            printres(row)

    if 0:
        for row in dom_select('<z><a><b>B1</b></a><b>B2</b></z>', 'z > b'):
            printres(row)

    if 0:
        # for row in dom_select('<z><a><b>B1</b></a><b>B2</b><c>C1</c><b>B3</b></z>', 'a + b'):
        for row in dom_select('<a>A1</a><a>A2</a><a>A3</a><a>A4</a>', 'a + a + a'):
            printres(row)

    if 0:
        html = '<a><b>B0</b></b>' + \
                '<a><b>B1</b><b>B2</b></a><a><b>B3</b><c>C2</c></a><a><c>C1</c><b>B4</b></a>' + \
                '<a><c>C3</c><b>B5</b><b>B6</b><c>C4</c></a>'
        for pclass in (':first-child', ':last-child', ':first-of-type', ':last-of-type',
                       ':first-child:last-child', ':first-of-type:last-of-type'):
            print(pclass)
            for row in dom_select(html, 'a b{}'.format(pclass)):
                printres(row)
        print('b + b:first-of-type')
        for row in dom_select('<b>B1</b><b>B2</b>', 'b + b:first-of-type'):
            printres(row)

    if 0:
        for row in dom_select('<a>A1</a><a disabled>A2</a><a disabled="disabled">A3</a>', 'a:disabled'):
            printres(row)
