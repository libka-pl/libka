from itertools import tee, zip_longest


# see https://docs.python.org/3/library/itertools.html
def pairwise(iterable):
    "Pair iterator: s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def pairwise_longest(iterable, fillvalue=None):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip_longest(a, b, fillvalue=fillvalue)


def pairprev(iterable, fillvalue=None):
    "s -> (None,s0), (s0,s1), (s1,s2), ..."
    a, b = tee(iterable)
    try:
        yield fillvalue, next(b)
    except StopIteration:
        return
    # yield from zip(a, b)
    for x in zip(a, b):  # TODO: Remove this after drop PY2
        yield x


def pairnext(iterable, fillvalue=None):
    "s -> (s0,s1), (s1,s2), ... (sn, None)"
    a, b = tee(iterable)
    next(b, None)
    return zip_longest(a, b, fillvalue=fillvalue)


def neighbor_iter(iterable, fillvalue=None):
    "s -> (None,s0,s1), (s0,s1,s2), ..., (sn-1, sn, None)"
    a, b, c = tee(iterable, 3)
    next(c, None)
    try:
        yield fillvalue, next(b), next(c, fillvalue)
    except StopIteration:
        return
    while True:
        try:
            yield next(a), next(b), next(c, fillvalue)
        except StopIteration:
            return
