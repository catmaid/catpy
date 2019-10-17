import sys

try:
    from tqdm import tqdm
except ImportError:
    class tqdm(object):
        def __init__(self, iterable, *args, **kwargs):
            self.iterable = iterable

        def __iter__(self):
            return iter(self.iterable)

        def write(self, s):
            sys.stdout.write(s)
