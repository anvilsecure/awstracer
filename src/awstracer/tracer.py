import datetime
import shlex
import textwrap

import awscli
import awscli.clidriver as clidriver
import botocore
import botocore.hooks
from awscli.plugin import load_plugins

from .utils import convert_from_camelcase, json_dumps


class Trace:
    def __init__(self):
        self.request_id = "<not set>"
        self.fn_name = "<not set>"
        self.inparams = {}
        self.outparams = {}
        self.ts_start = None
        self.ts_end = None

    def start(self):
        self.ts_start = datetime.datetime.now()

    def finish(self):
        self.ts_end = datetime.datetime.now()

    def get_output_value(self, name):
        names = name.split(".")
        d = self.outparams
        for name in names:
            if name not in d:
                return None
            d = d[name]
        return d

    def set_input(self, fn_name, params):
        self.fn_name = fn_name
        self.inparams = params

    def set_output(self, request_id, fn_name, values):
        if fn_name != self.fn_name:
            raise ValueError("unexpected call with non-matching function names")
        self.fn_name = fn_name
        self.request_id = request_id
        self.outparams = values

    def to_dict(self):
        return {
            "request_id": self.request_id,
            "fn_name": self.fn_name,
            "inparams": self.inparams,
            "outparams": self.outparams,
            "ts_start": self.ts_start,
            "ts_end": self.ts_end
        }

    @staticmethod
    def from_dict(d):
        obj = Trace()
        for n in ("request_id", "fn_name", "inparams", "outparams", "ts_start", "ts_end"):
            if n not in d:
                raise ValueError("invalid input")
            setattr(obj, n, d[n])
        return obj

    def get_shell_var(self, name, val):
        optname = shlex.quote("--{}".format(convert_from_camelcase(name)))

        if type(val) == dict or type(val) == list:
            val = json_dumps(val, pretty=False)
        elif type(val) == str:
            val = str(val)
        else:
            raise NotImplementedError("{}".format(type(val)))

        optval = shlex.quote(val)
        return (optname, optval)

    def get_shell_poc(self, replace_vars={}):
        parts = self.fn_name.split(".")
        if len(parts) != 2:
            raise ValueError("invalid fn_name")
        resource, fn = parts

        args = ["aws", resource, convert_from_camelcase(fn)]
        for n in self.inparams:
            var = self.inparams[n] if n not in replace_vars else replace_vars[n]
            optname, optval = self.get_shell_var(n, var)
            args.append(optname)
            args.append(optval)
        return " ".join(args)

    def __str__(self):
        in_str, out_str = [], []
        for i in self.inparams:
            in_str.append("{}: {}".format(i, self.inparams[i]))
        for i in self.outparams:
            out_str.append("{}: {}".format(i, self.outparams[i]))

        return "Trace\n  ID: {} \n  API: {}\n  IN:\n{}\n  OUT:\n{}\n".format(
            self.request_id, self.fn_name,
            textwrap.indent("\n".join(in_str), "    "),
            textwrap.indent("\n".join(out_str), "    "))


class EventCapturer(botocore.hooks.HierarchicalEmitter):
    def __init__(self):
        super().__init__()
        self.trace = Trace()
        self.events_captured = []

    def emit(self, event_name, **kwargs):
        if event_name.startswith("provide-client-params"):
            fn_name = event_name[len("provide-client-params") + 1:]
            if len(fn_name) == 0:
                raise ValueError("unexpected fn name")
            if "params" not in kwargs:
                raise ValueError("unexpected input")
            params = kwargs["params"]
            self.trace.start()
            self.trace.set_input(fn_name, params)
        elif event_name.startswith("after-call"):
            fn_name = event_name[len("after-call") + 1:]
            if len(fn_name) == 0:
                raise ValueError("unexpected fn name")
            if "parsed" not in kwargs:
                raise ValueError("unexpected input")
            parsed = kwargs["parsed"]
            if "ResponseMetadata" not in parsed:
                raise ValueError("unexpected input")
            if "RequestId" not in parsed["ResponseMetadata"]:
                raise ValueError("unexpected input")
            req_id = parsed["ResponseMetadata"]["RequestId"]
            del parsed["ResponseMetadata"]
            self.trace.set_output(req_id, fn_name, parsed)
            self.trace.finish()
        self.events_captured.append(event_name)
        return super().emit(event_name, **kwargs)


class TraceRunner:
    def __init__(self):
        pass

    def run_aws_cmd(self, args):
        try:
            ev = EventCapturer()
            driver = self._create_clidriver(ev)
            retval = driver.main(args=args)
            # command failed so we don't record this trace and
            # can now simply bail out
            if retval != 0:
                return None
        except Exception as e:
            print("unknown exception occured: {}".format(str(e)))
            return None
        return ev.trace

    def _create_clidriver(self, ev):
        session = botocore.session.Session(awscli.EnvironmentVariables)
        # registering the event emitter needs to be done here immediately to
        # prevent argparsing errors
        session.register_component("event_emitter", ev)
        awscli.clidriver._set_user_agent_for_session(session)
        load_plugins(session.full_config.get('plugins', {}),
                     event_hooks=session.get_component('event_emitter'))
        driver = clidriver.CLIDriver(session=session)
        return driver
