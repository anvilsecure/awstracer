import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone


# This function taken from Python 3.7+ core distribution in Lib/datetime.py
def _parse_hh_mm_ss_ff(tstr):
    # Parses things of the form HH[:MM[:SS[.fff[fff]]]]
    len_str = len(tstr)

    time_comps = [0, 0, 0, 0]
    pos = 0
    for comp in range(0, 3):
        if (len_str - pos) < 2:
            raise ValueError("Incomplete time component")

        time_comps[comp] = int(tstr[pos:pos + 2])

        pos += 2
        next_char = tstr[pos:pos + 1]

        if not next_char or comp >= 2:
            break

        if next_char != ":":
            raise ValueError("Invalid time separator: %c" % next_char)

        pos += 1

    if pos < len_str:
        if tstr[pos] != ".":
            raise ValueError("Invalid microsecond component")
        else:
            pos += 1

            len_remainder = len_str - pos
            if len_remainder not in (3, 6):
                raise ValueError("Invalid microsecond component")

            time_comps[3] = int(tstr[pos:])
            if len_remainder == 3:
                time_comps[3] *= 1000

    return time_comps


# This function taken from Python 3.7+ core distribution in Lib/datetime.py
def _parse_isoformat_time(tstr):
    # Format supported is HH[:MM[:SS[.fff[fff]]]][+HH:MM[:SS[.ffffff]]]
    len_str = len(tstr)
    if len_str < 2:
        raise ValueError("Isoformat time too short")

    # This is equivalent to re.search("[+-]", tstr), but faster
    tz_pos = (tstr.find("-") + 1 or tstr.find("+") + 1)
    timestr = tstr[:tz_pos - 1] if tz_pos > 0 else tstr

    time_comps = _parse_hh_mm_ss_ff(timestr)

    tzi = None
    if tz_pos > 0:
        tzstr = tstr[tz_pos:]

        # Valid time zone strings are:
        # HH:MM               len: 5
        # HH:MM:SS            len: 8
        # HH:MM:SS.ffffff     len: 15

        if len(tzstr) not in (5, 8, 15):
            raise ValueError("Malformed time zone string")

        tz_comps = _parse_hh_mm_ss_ff(tzstr)
        if all(x == 0 for x in tz_comps):
            tzi = timezone.utc
        else:
            tzsign = -1 if tstr[tz_pos - 1] == "-" else 1

            td = timedelta(hours=tz_comps[0], minutes=tz_comps[1],
                           seconds=tz_comps[2], microseconds=tz_comps[3])

            tzi = timezone(tzsign * td)

    time_comps.append(tzi)
    return time_comps


def _fromisoformat(dtstr):
    # starting in Python 3.7 this is built in so use that the rest is just a
    # fall-back so that we can use these utilities also on Python 3.6
    try:
        if getattr(datetime, "fromisoformat"):
            return datetime.fromisoformat(dtstr)
    except AttributeError:
        pass
    if len(dtstr) < 10 or dtstr[4] != "-" or dtstr[7] != "-" or dtstr[10] != "T":
        raise ValueError("invalid input")
    year, month, day = int(dtstr[0:4]), int(dtstr[5:7]), int(dtstr[8:10])
    date_components = [year, month, day]
    tstr = dtstr[11:]
    if tstr:
        time_components = _parse_isoformat_time(tstr)
    else:
        time_components = [0, 0, 0, 0, None]
    return datetime(*(date_components + time_components))


def json_serialize_helper(obj):
    if isinstance(obj, (datetime, date)):
        return {"_isoformat": obj.isoformat()}
    raise TypeError("Type {} is not serializable".format(type(obj)))


def json_deserialize_helper(obj):
    _isoformat = obj.get("_isoformat")
    if _isoformat is not None:
        return _fromisoformat(_isoformat)
    return obj


def json_dumps(obj, pretty=False):
    if pretty:
        return json.dumps(obj, sort_keys=True, indent=1, default=json_serialize_helper)
    return json.dumps(obj, default=json_serialize_helper)


def json_load(fd):
    return json.load(fd, object_hook=json_deserialize_helper)


def json_loads(s):
    return json.loads(s, object_hook=json_deserialize_helper)


def convert_from_camelcase(s):
    ret = [s[0].lower()]
    for i, k in enumerate(s):
        if i == 0:
            continue
        if k.isupper():
            if not s[i - 1].isupper():
                ret.append("-")
                ret.append(k.lower())
            elif i + 1 < len(s) and s[i + 1].isupper():
                ret.append(k.lower())
                ret.append("-")
            else:
                ret.append(k.lower())
        else:
            ret.append(k)
    return "".join(ret)


def convert_to_camelcase(s):
    if len(s) == 0:
        raise ValueError("unexpected input")
    ret = [s[0].upper()]
    i = 1
    while i < len(s):
        if s[i] == "-":
            if len(s) - 1 == i:
                raise ValueError("unexpected input")
            ret.append(s[i + 1].upper())
            i += 1
        else:
            ret.append(s[i])
        i += 1
    return "".join(ret)


def setup_logging(logger, debug=True, colorize=True):
    # configures basic formatting and colorization via ANSI terminal colors
    class LogFormatter(logging.Formatter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def format(self, record):
            result = logging.Formatter.format(self, record)
            if not result:
                return None
            if not colorize:
                return result
            if record.levelno == logging.DEBUG:
                c = "\x1b[90m"
            elif record.levelno == logging.ERROR:
                c = "\x1b[31m"
            elif record.levelno == logging.INFO:
                c = "\x1b[37m"
            elif record.levelno == logging.WARNING:
                c = "\x1b[33m"
            else:
                c = ""
            results = result.split("\x1b[0m")
            rep = "\x1b[0m"
            result = "{}{}{}".format(c, "{}{}".format(rep, c).join(results), rep)
            return result

    class LogHandler(logging.StreamHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def emit(self, record):
            return super().emit(record)

    logger.setLevel(logging.INFO if not debug else logging.DEBUG)
    handler = LogHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = LogFormatter('%(asctime)s - %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def process_file_argument(arg):
    if not arg.startswith("file://"):
        return arg
    arg_fn = arg[len("file://"):]
    try:
        with open(arg_fn, "rb") as fd:
            return fd.read().decode("utf-8")
    except Exception:
        return None
    return None
