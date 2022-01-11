
from typing import Union
from pathlib import Path
import argparse
try:
    # faster implementation
    from lxml import etree
except ModuleNotFoundError:
    # standard implementation
    from xml.etree import ElementTree as etree


class Addon:
    """Simple Kodi addon description."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self._root = None

    def is_valid(self):
        """True, if addon has "addon.xml" file."""
        path = self.path / 'addon.xml'
        return path.exists()

    @property
    def root(self):
        """Returns addon.xml root XML node."""
        if self._root is None:
            path = self.path / 'addon.xml'
            xml = etree.parse(str(path))
            root = xml.getroot()
            if root.tag != 'addon':
                raise TypeError(f'Addon {self.path} is NOT valid')
            self._root = root
        return self._root


def generate(*paths):
    """
    Gnerate repo <addons/> node from all given paths.
    Path point to addon or foler with addons.
    """
    repo = etree.Element('addons')
    for path in paths:
        path = Path(path)
        if (addon := Addon(path)).is_valid():
            repo.append(addon.root)
        else:
            for p in path.iterdir():
                if (addon := Addon(p)).is_valid():
                    repo.append(addon.root)
    return repo


def process(*paths, output: Union[str, Path]):
    """Process paths. Generate XML and write addons.xml."""
    repo = generate(*paths)
    with open(output, 'wb') as f:
        etree.ElementTree(repo).write(f)


def main(argv: list[str] = None):
    """Main entry."""
    p = argparse.ArgumentParser(description='Kodi repo ganerator')
    p.add_argument('--output', '-o', default='addons.xml', help='output addons.xml file')
    p.add_argument('path', metavar='PATH', nargs='+', help='path to addon or folder with addons')
    args = p.parse_args(argv)
    process(*args.path, output=args.output)


if __name__ == '__main__':
    main()
