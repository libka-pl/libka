#!/usr/bin/env python3

import sys
import os
import re
from pathlib import Path
import subprocess
from collections import namedtuple

prog, sys.argv[0] = sys.argv[0], 'pdoc3'
from pdoc.cli import main as pdoc_main, parser as pdoc_arg_parser  # noqa E402
sys.argv[0] = prog


TOP = Path(__file__).resolve().parent.parent


Link = namedtuple('Link', 'regex link')


def remod(mods, link, func_link=None):
    entry = link
    if link.startswith('https') or link.startswith('http'):
        link = fr'<a href="{link}"><code>\1</code></a>'
    yield Link(re.compile(fr'<code>({"|".join(mods)})</code>'), link)
    if func_link is not None:
        link = func_link
        if link.startswith('#'):
            link = entry + link
        if link.startswith('https') or link.startswith('http'):
            link = fr'<a href="{link}"><code>\1.\2</code></a>'
        yield Link(re.compile(fr'<code>({"|".join(mods)})\.(\w+)</code>'), link)


BUILTIN = ['abc', 'aifc', 'argparse', 'ast', 'asynchat', 'asyncio', 'asyncore', 'audioop', 'base64', 'bdb',
           'binhex', 'bisect', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmd', 'code', 'codecs', 'codeop',
           'collections', 'collections.abc', 'colorsys', 'compileall', 'concurrent', 'concurrent.futures',
           'configparser', 'contextlib', 'contextvars', 'copy', 'copyreg', 'crypt', 'csv', 'ctypes', 'curses',
           'curses.ascii', 'curses.panel', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib', 'dis',
           'distutils', 'doctest', 'email', 'email.charset', 'email.contentmanager', 'email.encoders',
           'email.errors', 'email.generator', 'email.header', 'email.headerregistry', 'email.iterators',
           'email.message', 'email.mime', 'email.parser', 'email.policy', 'email.utils', 'ensurepip', 'enum',
           'filecmp', 'fileinput', 'fnmatch', 'fractions', 'ftplib', 'functools', 'getopt', 'getpass', 'gettext',
           'glob', 'graphlib', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'html.entities', 'html.parser', 'http',
           'http.client', 'http.cookiejar', 'http.cookies', 'http.server', 'imaplib', 'imghdr', 'imp',
           'importlib', 'importlib.metadata', 'inspect', 'io', 'ipaddress', 'json', 'keyword', 'linecache',
           'locale', 'logging', 'logging.config', 'logging.handlers', 'lzma', 'mailbox', 'mailcap', 'mimetypes',
           'mmap', 'modulefinder', 'multiprocessing', 'multiprocessing.shared_memory', 'netrc', 'nis', 'nntplib',
           'numbers', 'operator', 'optparse', 'os', 'os.path', 'ossaudiodev', 'pathlib', 'pdb', 'pickle',
           'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib', 'poplib', 'pprint', 'profile', 'pty',
           'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're', 'readline', 'reprlib', 'resource',
           'rlcompleter', 'runpy', 'sched', 'secrets', 'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site',
           'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'sqlite3', 'ssl', 'stat', 'statistics',
           'string', 'stringprep', 'struct', 'subprocess', 'sunau', 'symtable', 'sysconfig', 'tabnanny',
           'tarfile', 'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading', 'timeit', 'tkinter',
           'tkinter.colorchooser', 'tkinter.dnd', 'tkinter.font', 'tkinter.messagebox', 'tkinter.scrolledtext',
           'tkinter.tix', 'tkinter.ttk', 'token', 'tokenize', 'trace', 'traceback', 'tracemalloc', 'tty',
           'turtle', 'types', 'typing', 'unittest', 'unittest.mock', 'urllib', 'urllib.error', 'urllib.parse',
           'urllib.request', 'urllib.robotparser', 'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref',
           'webbrowser', 'wsgiref', 'xdrlib', 'xml', 'xml.dom', 'xml.dom.minidom', 'xml.dom.pulldom', 'xml.sax',
           'xml.sax.handler', 'xmlrpc', 'xmlrpc.client', 'xmlrpc.server', 'zipapp', 'zipfile', 'zipimport',
           'zoneinfo']

# READTHEDOCS = ['requests']

LINKS = [
    Link(re.compile('<code>&lt;(https://.*?)&gt;</code>'), r'<a href="\1"><code>\1</code></a>'),
    *remod(BUILTIN, r'https://docs.python.org/3/library/\1.html', r'#\1.\2'),
    *remod(['requests'],
           r'https://\1.readthedocs.io/en/latest/',
           r'https://docs.python-\1.org/en/latest/api/#\1.\2'),
    *remod(['aiohttp'],
           r'https://docs.aiohttp.org/en/stable/index.html',
           r'https://docs.aiohttp.org/en/stable/client_reference.html#=\1.\2'),
    *remod(['yarl'],
           r'https://\1.readthedocs.io/en/latest/api.html',
           r'https://\1.readthedocs.io/en/latest/api.html#\1.\2'),
    *remod(['multidict'],
           r'https://\1.readthedocs.io/en/latest/api.html',
           r'https://\1.readthedocs.io/en/latest/\1.html#\1.\2'),
]


def run_pdoc(*modules, out='html'):
    """Run pdoc3 main."""
    modules = [f'{m}/' for m in modules]
    argv = ['--output-dir', str(TOP / Path(out)), '--html', '--force', *modules]
    print(argv)
    print(pdoc_arg_parser)
    try:
        cd = Path(os.curdir).resolve()
        os.chdir(TOP / 'script.module.libka' / 'lib')
        print(pdoc_arg_parser.parse_args(argv))
        pdoc_main(pdoc_arg_parser.parse_args(argv))
    finally:
        os.chdir(cd)


def tune_html(path='html'):
    def replace(r):
        return r.group(0)

    path = TOP / Path(path)
    for path in path.glob('**/*.html'):
        with open(path) as f:
            src = data = f.read()
        for link in LINKS:
            data = link.regex.sub(link.link, data)
        if src != data:
            with open(path, 'w') as f:
                f.write(data)


def rsync(*modules, path='html', remote='kodi:/home/kodi/libka/doc'):
    path = TOP / Path(path)
    for mod in modules:
        args = ['rsync', '-Pah', '--delete', '--stats', '-e', 'ssh', f'{path / mod}/', f'{remote}/{mod}/']
        print(' '.join(args))
        subprocess.run(args)


def run():
    run_pdoc('libka')
    tune_html()
    rsync('libka')


def main(argv=None):
    run()


if __name__ == '__main__':
    main()
