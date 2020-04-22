import argparse
import os
import readline
import shlex

from .tracer import TraceRunner
from .utils import json_dumps, process_file_argument


class TraceRecorder(TraceRunner):
    def __init__(self, filename, prompt_on_save=True):
        super().__init__()
        if filename is None:
            raise ValueError("need a filename to save to")
        self._filename = filename
        self.traces = []
        self.prompt_on_save = prompt_on_save

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.prompt_on_save:
            if not confirm_prompt("Save cached trace to {}?".format(self._filename)):
                return
        with open(self._filename, "wb") as fd:
            data = []
            for trace in self.traces:
                data.append(trace.to_dict())
            data = json_dumps(data, pretty=True)
            fd.write(data.encode("utf-8"))

    def process_file_arguments(self, args):
        ret = []
        for arg in args:
            arg_ret = process_file_argument(arg)
            if not arg_ret:
                print("Couldn't read {}".format(arg))
                return None
            ret.append(arg_ret)
        return ret

    def run_aws_cmd(self, args):
        args = self.process_file_arguments(args)
        if not args:
            return
        trace = super().run_aws_cmd(args)
        if not trace:
            return
        save = True
        if self.prompt_on_save:
            save = confirm_prompt("Add command to trace cache?")
        if save:
            self.traces.append(trace)


def confirm_prompt(prompt):
    while True:
        answer = input("{} [y/N]: ".format(prompt)).lower()
        if answer == "" or answer == "n":
            return False
        elif answer == "y":
            return True
        else:
            continue


def run_misc_cmd(cmd, prompt=True):
    if prompt:
        if not confirm_prompt("Arbitrary shell command. Would you like to execute this anyway?"):
            return
    os.system(cmd)


def run(recorder, prompt_color=True, prompt_on_misc=True, enable_misc_cmd=True):
    try:
        readline.read_init_file()
    except Exception:
        # for some reason this fails on MacOS
        pass
    prompt = "\x1b[31m(rec)\x1b[0m " if prompt_color else "(rec) "
    multiline_prompt = "\x1b[31m>\x1b[0m " if prompt_color else "> "
    try:
        while True:
            cmd = input(prompt)

            # parse multiline commands and display a different prompt to denote
            # we're in multiline mode similarly to how bash does it
            if len(cmd) > 0 and cmd[-1] == "\\":
                parts = [cmd[:-1]]
                while True:
                    part = input(multiline_prompt)
                    if len(part) > 0 and part[-1] == "\\":
                        parts.append(part[:-1])
                        continue
                    parts.append(part)
                    break
                cmd = " ".join(parts)

            split_cmd = shlex.split(cmd)
            if len(split_cmd) == 0:
                continue
            if split_cmd[0] == "aws":
                recorder.run_aws_cmd(split_cmd[1:])
            else:
                if not enable_misc_cmd:
                    print("Can only record awscli commands.")
                    continue
                run_misc_cmd(cmd, prompt_on_misc)
    except EOFError:
        pass
    except KeyboardInterrupt:
        pass
    print("")


def opt_parser(args=None):
    parser = argparse.ArgumentParser(description="AWS CLI Trace Recorder")
    parser.add_argument("-c", action="store_false", dest="prompt_color", help="Turn off colorized output")
    parser.add_argument("-d", action="store_false", dest="prompt_on_misc", help="Do not ask for confirmation for shell execute")
    parser.add_argument("-n", action="store_false", dest="prompt_on_save", help="Do not prompt when adding to/saving trace files")
    parser.add_argument("-s", action="store_true", dest="enable_misc_cmd", help="Enable execution of all shell commands")
    group = parser.add_argument_group("required arguments")
    group.add_argument("--trace-file", metavar="FILE", type=str, required=True, help="output trace file", dest="trace_file")
    ns = parser.parse_args() if not args else parser.parse_args(args)
    return ns


def main():
    ns = opt_parser()

    with TraceRecorder(ns.trace_file, ns.prompt_on_save) as recorder:
        run(recorder,
            prompt_color=ns.prompt_color,
            prompt_on_misc=ns.prompt_on_misc,
            enable_misc_cmd=ns.enable_misc_cmd)


if __name__ == "__main__":
    main()
