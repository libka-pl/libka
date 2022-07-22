
from enum import IntEnum


class AspectRatio:
    Stretch = 0     # fill
    ScaleUp = 1     # crops
    ScaleDown = 2   # black bar

    # Qt-like names
    Fill = Stretch
    Keep = ScaleDown
    Expand = ScaleUp
