# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function

import sys as _sys
import argparse

from .mselect import dom_select
from .selectorparser import parse as selector_parse
from .selectorparser import dump as selector_dump
from .selectorparser import set_debug_repr as selector_set_debug_repr, set_debug as selector_set_debug


class ExtArgumentParser(argparse.ArgumentParser):
    r"""
    Extanded a bit ArgumentParser.

    New features:

    - set_default_subparser() - which subpurser should be used
                                if these is no subcommand in args

    - set_subparser_alternative() - any aternative for subcommand
                                    including --cmd
    """

    def __init__(self, *args, **kwargs):
        super(ExtArgumentParser, self).__init__(*args, **kwargs)
        self._default_subparser = None
        self._subparsers_alt = {}

    def set_default_subparser(self, defname):
        r"""Set default subparser (subcommand name)."""
        self._default_subparser = defname

    def set_subparser_alternative(self, name, *altnames):
        r"""
        Set subparser (subcommand name) alternative.
        Useful for ateratives with dashes.
        """
        for a in altnames:
            self._subparsers_alt[a] = name

    def _inject_default_subparser(self, argv):
        names = set(p for a in self._subparsers._actions
                    if isinstance(a, argparse._SubParsersAction)
                    for p in a._name_parser_map)
        for i, a in enumerate(argv):
            argv[i] = a = self._subparsers_alt.get(a, a)
            if not a.startswith('-'):
                if a not in names:
                    argv.insert(i, self._default_subparser)
                return
        argv.append(self._default_subparser)

    def parse_args(self, args=None, namespace=None):
        if args is None:
            # args default to the system args
            args = _sys.argv[1:]
        else:
            # make sure that args are mutable
            args = list(args)
        if self._default_subparser is not None:
            self._inject_default_subparser(args)
        return super(ExtArgumentParser, self).parse_args(args=args, namespace=namespace)

    #def parse_known_args(self, args=None, namespace=None):
    #    if args is None:
    #        # args default to the system args
    #        args = _sys.argv[1:]
    #    else:
    #        # make sure that args are mutable
    #        args = list(args)
    #    if self._default_subparser is not None:
    #        self._inject_default_subparser(args)
    #    return super(ExtArgumentParser, self).parse_known_args(args=args, namespace=namespace)


def main():
    print('=== Tests ===')

    import requests
    import pprint
    pprint = pprint.PrettyPrinter(indent=2).pprint

    aparser = ExtArgumentParser()
    aparser.add_argument('--debug', action='store_true', help='debug info')

    asubparsers = aparser.add_subparsers(dest='op')
    aparser.set_default_subparser('CMDURL')

    aurlparser = asubparsers.add_parser('CMDURL', help='(default) test selector on URL')
    aurlparser.add_argument('--flat', action='store_true', default=True, help='flat result')
    aurlparser.add_argument('--no-flat', '-F', action='store_false', dest='flat', help='nestet result')
    aurlparser.add_argument('url', metavar='URL', nargs=1, help='URL or file')
    aurlparser.add_argument('selectors', metavar='SEL', nargs='+', help='selector to parse')

    ahtmlparser = asubparsers.add_parser('CMDHTML', help='(-H) Use direct HTML instead of URL')
    ahtmlparser.add_argument('--flat', action='store_true', default=True, help='flat result')
    ahtmlparser.add_argument('--no-flat', '-F', action='store_false', dest='flat', help='nestet result')
    ahtmlparser.add_argument('html', metavar='HTML', nargs=1, help='Direct HTML instead of URL')
    ahtmlparser.add_argument('selectors', metavar='SEL', nargs='+', help='selector to parse')
    aparser.set_subparser_alternative('CMDHTML', '--html', '-H')

    aselparser = asubparsers.add_parser('CMDSEL', help='(-S) test selector parser')
    aselparser.add_argument('selectors', metavar='SEL', nargs='+', help='selector to parse')
    aparser.set_subparser_alternative('CMDSEL', '--selector', '--selector-parse', '-S')

    # cmdi = [x.title for x in aparser._action_groups].index('command')
    # aparser._action_groups.insert(0, aparser._action_groups.pop(cmdi))
    args = aparser.parse_args()

    if args.debug:
        print('CommandLine:', args)
        selector_set_debug_repr()
        selector_set_debug(True)

    if args.op == 'CMDSEL':
        selector_set_debug_repr()
        for sel in args.selectors:
            print(selector_parse(sel))
    elif args.op == 'CMDHTML':
        html = args.html[0]
        for sel in args.selectors:
            pprint(dom_select(html, sel, flat=args.flat))
    else:
        url = args.url[0]
        if url.startswith('file://'):
            url = url[7:]
        if '://' in url:
            with requests.Session() as sess:
                res = sess.get(url)
                page = res.text
        else:
            with open(url) as f:
                page = f.read()
        # print(page[:200])
        for sel in args.selectors:
            pprint(dom_select(page, sel, flat=args.flat))


if __name__ == '__main__':
    main()
