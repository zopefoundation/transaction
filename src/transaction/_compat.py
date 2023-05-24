def text_(s):
    if not isinstance(s, str):  # pragma: no cover
        s = s.decode('utf-8')
    return s


def native_(s, encoding='latin-1', errors='strict'):
    if isinstance(s, str):
        return s
    return str(s, encoding, errors)
