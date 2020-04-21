import argparse
import logging
import shlex
import sys
import time

from .tracer import Trace, TraceRunner
from .utils import convert_to_camelcase, json_load, setup_logging

logger = logging.getLogger(__name__)


class Edge:
    def __init__(self, trace_from, trace_to, varname_from, varname_to):
        self.trace_from = trace_from
        self.trace_to = trace_to
        self.varname_from = varname_from
        self.varname_to = varname_to

    def __str__(self):
        return "[{}] {} {} -> [{}] {} {}".format(
            self.trace_from.request_id,
            self.trace_from.fn_name,
            self.varname_from,
            self.trace_to.request_id,
            self.trace_to.fn_name,
            self.varname_to,
        )


class MatchingNameAndValueEdge(Edge):
    def __init__(self, trace_from, trace_to, varname_from):
        super().__init__(trace_from, trace_to, varname_from, varname_from)


class MatchingNameEdge(Edge):
    def __init__(self, trace_from, trace_to, varname_from, value_from, value_to):
        super().__init__(trace_from, trace_to, varname_from, varname_from)


class MatchingValueEdge(Edge):
    def __init__(self, trace_from, trace_to, varname_from, varname_to):
        super().__init__(trace_from, trace_to, varname_from, varname_to)


class TracePlayer(TraceRunner):
    def __init__(self, input_fd, profile=None, endpoint=None, region=None, prompt_color=True):
        super().__init__()
        self._fd = input_fd
        self.connections = []
        self.profile = None
        self.endpoint = None
        self.region = region
        self.prompt_color = prompt_color

    def __enter__(self):
        self.traces = [Trace.from_dict(t) for t in json_load(self._fd)]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return

    def print_prompt(self, data):
        prompt = "\x1b[32m(play)\x1b[0m {}" if self.prompt_color else "(play) {}"
        data = "\x1b[33m{}\x1b[0m".format(data) if self.prompt_color else data
        print(prompt.format(data))

    def play_trace(self, input_trace, dryrun=False, stop_on_error=True, sleep_delay=None):
        logger.debug("Playing trace: dryrun={}, stop_on_error={}, sleep_delay={}".format(dryrun, stop_on_error, sleep_delay))

        self._play_results = {}
        self._play_results[input_trace.request_id] = input_trace

        logger.debug("Running {} single traces".format(len(self.traces)))
        for i, trace in enumerate(self.traces):

            # this is where we figure out the time difference between two
            # subsequent traces so we can sleep the appropriate amount of time
            # between them
            if i > 0:

                # calculate sleep delay from the time difference in the loaded
                # trace if no specific sleep delay is specified
                if sleep_delay is None:
                    last_trace = self.traces[i - 1]
                    diff = trace.ts_start - last_trace.ts_end
                    secs = diff.total_seconds()
                    isecs = int(secs)
                else:
                    secs = sleep_delay
                    isecs = int(sleep_delay)
                if isecs > 0:
                    self.print_prompt("sleeping for {} second{}".format(isecs, "" if isecs < 2 else "s"))

                # We still sleep as we could be sleeping for .5 seconds as
                # sleeping for 0 seconds just looks stupid
                time.sleep(secs)

            ret = self.play_single_trace(trace, dryrun)
            if not ret and stop_on_error:
                break

    def play_single_trace(self, trace, dryrun=False):
        # find connections into this trace and replace the variables with
        # the cached results variables
        replace_vars = {}
        logger.debug("Playing single trace: fn_name={}, request_id={}, dryrun={}".format(trace.fn_name, trace.request_id, dryrun))
        missing, replaced = 0, 0
        for edge in self.connections:
            if edge.trace_to.request_id == trace.request_id:
                logger.debug("Found matching edge to this trace from: fn_name={}, request_id={}".format(edge.trace_from.fn_name, edge.trace_from.request_id))

                from_rid = edge.trace_from.request_id
                if from_rid not in self._play_results:
                    logger.warning("Previous results not found so cannot replace variables.")
                    logger.warning("The {} call probably failed.".format(edge.trace_from.fn_name))
                    missing += 1
                    continue

                rtrace = self._play_results[from_rid]
                name = edge.varname_from
                if name not in rtrace.outparams:
                    logger.warning("Couldn't find {} in previous request results.".format(name))
                    logger.warning("The {} call probably failed.".format(rtrace.fn_name))
                    missing += 1
                    continue

                val = rtrace.outparams[name]
                logger.debug("Replacing {} value with {} (was: {})".format(name, shlex.quote(val), shlex.quote(edge.trace_to.inparams[name])))
                replace_vars[name] = val
                replaced += 1

        logger.debug("Replacing {} out of {} parameters ({} failed to replace)".
                     format(replaced, missing + replaced, missing))
        base_poc = trace.get_shell_poc(replace_vars)
        override = []

        # add overriding variables
        if self.profile:
            override.append("--profile")
            override.append(shlex.quote(self.profile))
            logger.debug("Added --profile")
        if self.endpoint:
            override.append("--endpoint")
            override.append(shlex.quote(self.endpoint))
            logger.debug("Added --endpoint")
        if self.region:
            override.append("--region")
            override.append(shlex.quote(self.region))
            logger.debug("Added --region")
        poc = "{} {}".format(base_poc, " ".join(override))

        # highlight replaced variables in different color if requested
        outpoc = poc
        if self.prompt_color:
            for name in replace_vars:
                optname, optval = trace.get_shell_var(name, replace_vars[name])
                outpoc = outpoc.replace("{} {}".format(optname, optval),
                                        "\x1b[31m{} {}\x1b[0m".format(optname, optval))

        self.print_prompt(outpoc)

        if dryrun:
            return trace

        # shell split the arguments and remove the call to aws itself
        args = shlex.split(poc)
        if args[0] != "aws":
            raise ValueError("sanity check failed")
        del args[0]

        out_trace = self.run_aws_cmd(args)
        self._play_results[trace.request_id] = out_trace
        logger.debug("Ran trace and added results to the results cache")
        return out_trace

    def get_shell_poc(self):
        pocs = []
        for trace in self.traces:
            poc = trace.get_shell_poc()
            pocs.append(poc)
        return "\n".join(pocs)

    def find_trace_connections(self, trace_from, trace_to, name, val):
        if name in trace_from.outparams:
            if trace_from.outparams[name] == val:
                logger.debug("Found connection from {} [] to {} [] with matching parameter name {} and value {}".
                             format(trace_from.fn_name, trace_from.request_id, trace_to.fn_name, trace_to.request_id, name, val))
                c = MatchingNameAndValueEdge(trace_from, trace_to, name)
            else:
                logger.debug("Found connection from {} [] to {} [] with matching name {} but different values: {} vs {}".
                             format(trace_from.fn_name, trace_from.request_id, trace_to.fn_name, trace_to.request_id, name, val, trace_from.outparams[name]))
                c = MatchingNameEdge(trace_from, trace_to, name, trace_from.outparams[name], val)
            self.connections.append(c)
        else:
            for name2 in trace_from.outparams:
                if trace_from.outparams[name2] == val:
                    logger.debug("Found connection from {} [] to {} [] with matching value {} but different parameter names: {} vs {}".
                                 format(trace_from.fn_name, trace_from.request_id, trace_to.fn_name, trace_to.request_id, val, name, name2))
                    c = MatchingValueEdge(trace_to, trace_to, name2, name)
                    self.connections.append(c)

    def find_connections(self, input_trace):
        self.connections = []
        for i, trace in enumerate(self.traces):

            for name in input_trace.outparams:
                val = input_trace.outparams[name]
                self.find_trace_connections(input_trace, trace, name, val)
            if i == 0:
                continue

            for name in trace.inparams:
                val = trace.inparams[name]
                for j, older_trace in enumerate(self.traces):
                    if j == i:
                        break
                    self.find_trace_connections(older_trace, trace, name, val)

    def prune_connections(self):
        # Assumption is that connections are sorted in the order of the loaded
        # tracefiles by find_connections(). We create a keyname of the unique
        # request id's and the variable name that the edge points too. If if is
        # already in the pruned dictionary it means we found an older
        # connection in the tracefile that already supplies this value and as
        # such we can ignore the new one.
        pruned = {}
        before_cnt = len(self.connections)
        prune_cnt = 0
        for i, edge in enumerate(self.connections):
            keyname = "{}.{}".format(edge.trace_to.request_id, edge.varname_to)
            if keyname in pruned:
                prune_cnt += 1
                continue
            pruned[keyname] = edge

        self.connections = list(pruned.values())
        after_cnt = len(self.connections)
        logger.debug("Pruned {} connections from total of {} so now {} left".format(prune_cnt, before_cnt, after_cnt))


def opt_parser(args=None):
    parser = argparse.ArgumentParser(description="AWS CLI Trace Player")
    parser.add_argument("--dryrun", action="store_true", dest="dryrun", help="Show trace and computed parameter substituations without actually executing them")
    parser.add_argument("--endpoint", metavar="URL", type=str, help="AWS endpoint url to use", dest="endpoint")
    parser.add_argument("--param", nargs=2, metavar=("NAME", "VALUE"), type=str, help="Override parameter NAME with VALUE", action="append", dest="params")
    parser.add_argument("--profile", metavar="PROFILE", type=str, help="AWS profile to run trace under", dest="profile")
    parser.add_argument("--region", metavar="REGION", type=str, help="AWS region to run trace in", dest="region")
    parser.add_argument("-s", type=int, metavar="N", dest="sleep_delay", default=None, help="Force N seconds of sleep delay between commands")
    parser.add_argument("-c", action="store_false", dest="colorize", help="Turn off colorized output")
    parser.add_argument("-d", action="store_true", dest="debug", help="Turn on debug output")
    parser.add_argument("-f", action="store_false", dest="stop_on_error", help="Continue running even if one or more commands fail")
    group = parser.add_argument_group("required arguments")
    group.add_argument("--trace-file", metavar="FILE", type=str, required=True, help="output trace file", dest="trace_file")
    ns = parser.parse_args() if not args else parser.parse_args(args)
    if ns.sleep_delay and ns.sleep_delay < 0:
        sys.stderr.write("sleep delay cannot be negative\n")
        sys.stderr.flush()
        sys.exit(1)
    return ns


def main():
    ns = opt_parser()
    setup_logging(logger, debug=ns.debug, colorize=ns.colorize)

    # add the overridden parameters to the input trace
    input_args = {}
    if ns.params:
        for name, val in ns.params:
            cname = convert_to_camelcase(name)
            input_args[cname] = val
            logger.debug("Adding {} to input for {} with value {}".format(name, cname, val))
    input_trace = Trace()
    input_trace.set_output("special-start-input-trace", "<not set>", input_args)

    try:
        with open(ns.trace_file, "rb") as fd:
            with TracePlayer(
                    input_fd=fd,
                    prompt_color=ns.colorize,
                    profile=ns.profile,
                    endpoint=ns.endpoint,
                    region=ns.region) as player:
                player.find_connections(input_trace)
                player.prune_connections()

                player.play_trace(input_trace, dryrun=ns.dryrun, stop_on_error=ns.stop_on_error, sleep_delay=ns.sleep_delay)
    except OSError:
        logger.error("Failed to open {}".format(ns.trace_file))
        sys.exit(1)

if __name__ == "__main__":
    main()
