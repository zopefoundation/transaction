import sys


PY3 = sys.version_info[0] == 3
JYTHON = sys.platform.startswith('java')

if PY3:
    text_type = str
else: # pragma: no cover
    # py2
    text_type = unicode

def bytes_(s, encoding='latin-1', errors='strict'):
    if isinstance(s, text_type):
        s = s.encode(encoding, errors)
    return s

def text_(s):
    if not isinstance(s, text_type):
        s = s.decode('utf-8')
    return s

if PY3:
    def native_(s, encoding='latin-1', errors='strict'):
        if isinstance(s, text_type):
            return s
        return str(s, encoding, errors)
else:  # pragma: no cover
    def native_(s, encoding='latin-1', errors='strict'):
        if isinstance(s, text_type):
            return s.encode(encoding, errors)
        return str(s)

if PY3:
    from io import StringIO
else: # pragma: no cover
    from io import BytesIO
    # Prevent crashes in IPython when writing tracebacks if a commit fails
    # ref: https://github.com/ipython/ipython/issues/9126#issuecomment-174966638
    class StringIO(BytesIO):
        def write(self, s):
            s = native_(s, encoding='utf-8')
            super(StringIO, self).write(s)


if PY3:
    def reraise(tp, value, tb=None):
        if value.__traceback__ is not tb: # pragma: no cover
            raise value.with_traceback(tb)
        raise value

else: # pragma: no cover
    def exec_(code, globs=None, locs=None):
        """Execute code in a namespace."""
        if globs is None:
            frame = sys._getframe(1)
            globs = frame.f_globals
            if locs is None:
                locs = frame.f_locals
            del frame
        elif locs is None:
            locs = globs
        exec("""exec code in globs, locs""")

    exec_("""def reraise(tp, value, tb=None):
    raise tp, value, tb
""")


try:
    from threading import get_ident as get_thread_ident
except ImportError: # pragma: no cover
    # py2
    from thread import get_ident as get_thread_ident
