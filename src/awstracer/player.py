import argparse
import logging
import shlex
import sys
import time

from .tracer import Trace, TraceRunner
from .utils import convert_to_camelcase, json_load, setup_logging, process_file_argument

logger = logging.getLogger("player")


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
    def __init__(self, trace_from, trace_to, varname, value):
        super().__init__(trace_from, trace_to, varname, varname)
        logger.debug("Connection from {} [{}] to {} [{}] with match for name {} and value {}".
                     format(trace_from.fn_name, trace_from.request_id, trace_to.fn_name, trace_to.request_id, varname, value))


class MatchingNameEdge(Edge):
    def __init__(self, trace_from, trace_to, varname, value_from, value_to):
        super().__init__(trace_from, trace_to, varname, varname)
        logger.debug("Connection from {} [{}] to {} [{}] with match for name {} but different values: {} -> {})".
                     format(trace_from.fn_name, trace_from.request_id, trace_to.fn_name, trace_to.request_id, varname, value_from, value_to))


class MatchingValueEdge(Edge):
    def __init__(self, trace_from, trace_to, value, varname_from, varname_to):
        super().__init__(trace_from, trace_to, varname_from, varname_to)
        logger.debug("Connection from {} [{}] to {} [{}] with match values {} but different names: {} -> {})".
                     format(trace_from.fn_name, trace_from.request_id, trace_to.fn_name, trace_to.request_id, value, varname_from, varname_to))


class TracePlayer(TraceRunner):
    def __init__(self, input_fd, input_args={}, profile=None, endpoint=None, region=None, prompt_color=True):
        super().__init__()
        self._fd = input_fd
        self._input_args = input_args
        self.connections = []
        self.profile = profile
        self.endpoint = endpoint
        self.region = region
        self.prompt_color = prompt_color

    def __enter__(self):
        traces = [Trace.from_dict(t) for t in json_load(self._fd)]
        input_trace = self._get_input_trace(traces)
        traces.insert(0, input_trace)
        self.traces = traces
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return

    def print_prompt(self, data):
        prompt = "\x1b[32m(play)\x1b[0m {}" if self.prompt_color else "(play) {}"
        data = "\x1b[33m{}\x1b[0m".format(data) if self.prompt_color else data
        print(prompt.format(data))

    def _get_input_trace(self, traces):
        # add all the toplevel-only unique input parameters
        args = set()
        for trace in traces:
            for name in trace.inparams:
                args.add(name)

        # check if there are no erroneous input arguments specified, we will continue
        # anyway but we at least give the user the option to detect this
        for iarg in self._input_args:
            if iarg not in args:
                logger.warning("Invalid argument {}: not found in the inputs for any of the traces".format(iarg))

        output_args = {}
        for arg in args:
            output_args[arg] = self._input_args.get(arg, None)
        ret = Trace()
        ret.start()
        ret.set_input("<api>.<fn_name>", {})
        ret.set_output("special-start-input-trace", "<api>.<fn_name>", output_args)
        ret.finish()
        return ret

    def play_trace(self, dryrun=False, stop_on_error=True, sleep_delay=None):
        logger.debug("Playing trace: dryrun={}, stop_on_error={}, sleep_delay={}".format(dryrun, stop_on_error, sleep_delay))

        t0 = self.traces[0]
        self._play_results = {}
        self._play_results[t0.request_id] = t0

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
                # sleeping for 0 seconds just looks stupid. The seconds could
                # be negative due to timezone changes or because of the
                # automatically inserted first trace which will by definition
                # be created at a later date than the list of traces
                # themselves.
                if secs > 0:
                    time.sleep(secs)

            ret = self.play_single_trace(trace, dryrun, i == 0)
            if not ret and stop_on_error:
                break

    def play_single_trace(self, trace, dryrun=False, is_first=False):
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

                # check if we can fetch results from the previous call
                rtrace = self._play_results[from_rid]
                if not rtrace:
                    logger.warning("The {} call probably failed.".format(edge.trace_from.fn_name))
                    missing += 1
                    continue

                # check if we found a value for the connection
                from_name = edge.varname_from
                to_name = edge.varname_to
                old_val = edge.trace_to.inparams[to_name]
                val = rtrace.get_output_value(from_name)
                if val:
                    logger.debug("Replacing {} value with {} (was: {})".format(to_name, shlex.quote(val), shlex.quote(old_val)))
                    replace_vars[to_name] = val
                    replaced += 1
                    continue

                logger.warning("Couldn't replace {} as we didn't find {} (was: {})".format(to_name, from_name, shlex.quote(old_val)))
                missing += 1

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

        if not is_first:
            self.print_prompt(outpoc)

        if dryrun or is_first:
            self._play_results[trace.request_id] = trace
            return trace

        # shell split the arguments and remove the call to aws itself
        args = shlex.split(poc)
        if args[0] != "aws":
            raise ValueError("sanity check failed")
        del args[0]

        # process any file arguments if needed
        new_args = []
        for arg in args:
            arg_ret = process_file_argument(arg)
            if not arg_ret:
                logger.error("Couldn't read {}".format(arg))
                return None
            new_args.append(arg_ret)

        out_trace = self.run_aws_cmd(new_args)
        self._play_results[trace.request_id] = out_trace
        logger.debug("Ran trace and added results to the results cache")
        return out_trace

    def get_shell_poc(self):
        pocs = []
        for trace in self.traces:
            poc = trace.get_shell_poc()
            pocs.append(poc)
        return "\n".join(pocs)

    def find_connections_between_traces(self, trace_from, trace_to):
        logger.debug("Finding connections from {} to {}".format(trace_from.fn_name, trace_to.fn_name))
        for name_out in trace_from.outparams:
            val_from = trace_from.outparams[name_out]
            if not val_from:
                continue

            if type(val_from) == dict:
                # check nested structure XXX for now we only check one level deep
                for kname in val_from:
                    nested_name = "{}.{}".format(name_out, kname)
                    kval = val_from[kname]
                    for k in trace_to.inparams:
                        inval = trace_to.inparams[k]
                        if inval == kval:
                            c = MatchingValueEdge(trace_from, trace_to, kval, nested_name, k)
                            self.connections.append(c)

            # check if we can find a matching parameter name between the output
            # of the trace we're coming from and the input parameters of the
            # trace we're comparing with
            if name_out in trace_to.inparams:
                val_to = trace_to.inparams[name_out]
                if val_from == val_to:
                    c = MatchingNameAndValueEdge(trace_from, trace_to, name_out, val_to)
                else:
                    c = MatchingNameEdge(trace_from, trace_to, name_out, val_from, val_to)
                self.connections.append(c)
                continue

            # check if we can find a matching input value even though the
            # parameter names are different compared with the output value of
            # the trace we're coming from
            for name_in in trace_to.inparams:
                val_to = trace_to.inparams[name_in]
                if val_from == val_to:
                    c = MatchingValueEdge(trace_from, trace_to, val_to, name_out, name_in)
                    self.connections.append(c)
                # we keep going as we technically could have multiple
                # parameters which are set to the same value

    def find_connections(self):
        self.connections = []
        for i, trace in enumerate(self.traces):
            for j, older_trace in enumerate(self.traces):
                if j == i:
                    break
                self.find_connections_between_traces(older_trace, trace)

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
    parser.add_argument("-p", "--param", nargs=2, metavar=("NAME", "VALUE"), type=str, help="Override parameter NAME with VALUE", action="append", dest="params")
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

    # add the overridden parameters to the input
    input_args = {}
    if ns.params:
        for name, val in ns.params:
            cname = convert_to_camelcase(name)
            input_args[cname] = val
            logger.debug("Adding {} to input for {} with value {}".format(name, cname, val))

    if not ns.sleep_delay and ns.dryrun:
        logger.debug("Turning off sleep delay automatically as we are doing a dryrun")
        ns.sleep_delay = 0

    try:
        with open(ns.trace_file, "rb") as fd:
            with TracePlayer(
                    input_fd=fd,
                    input_args=input_args,
                    prompt_color=ns.colorize,
                    profile=ns.profile,
                    endpoint=ns.endpoint,
                    region=ns.region) as player:

                player.find_connections()
                player.prune_connections()

                player.play_trace(dryrun=ns.dryrun, stop_on_error=ns.stop_on_error, sleep_delay=ns.sleep_delay)
    except OSError:
        logger.error("Failed to open {}".format(ns.trace_file))
        sys.exit(1)


if __name__ == "__main__":
    main()
