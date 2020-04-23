import io
import unittest
from contextlib import redirect_stderr, redirect_stdout


class TestPlayer(unittest.TestCase):
    def test_options(self):
        try:
            from awstracer.player import opt_parser
        except Exception:
            self.fail("cannot import opt_parser")
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()):
                with redirect_stderr(io.StringIO()):
                    opt_parser([])
                    # sleep delay cannot be negative so should exit
                    opt_parser(["--trace-file", "bla", "-s", "-1"])
        ns = opt_parser(["--trace-file", "bla"])
        self.assertEqual(ns.trace_file, "bla")
        # check default settings for options
        self.assertIsNone(ns.endpoint)
        self.assertIsNone(ns.params)
        self.assertIsNone(ns.profile)
        self.assertIsNone(ns.region)
        self.assertFalse(ns.dryrun)
        self.assertFalse(ns.debug)
        self.assertIsNone(ns.sleep_delay)
        self.assertTrue(ns.colorize)
        self.assertTrue(ns.stop_on_error)
        ns = opt_parser(["--trace-file", "bla", "--dryrun", "--region", "bl1", "--profile", "bl2", "--endpoint", "bl3", "-s", "2", "-d", "-f", "-c"])
        self.assertTrue(ns.dryrun)
        self.assertEqual(ns.region, "bl1")
        self.assertEqual(ns.profile, "bl2")
        self.assertEqual(ns.endpoint, "bl3")
        self.assertEqual(ns.sleep_delay, 2)
        self.assertTrue(ns.debug)
        self.assertFalse(ns.colorize)
        self.assertFalse(ns.stop_on_error)
        ns = opt_parser(["--trace-file", "bla", "--param", "p1", "val1", "--param", "p2", "val2"])
        self.assertIsInstance(ns.params, list)
        self.assertEqual(len(ns.params), 2)
        self.assertEqual(ns.params[0][0], "p1")
        self.assertEqual(ns.params[0][1], "val1")
        self.assertEqual(ns.params[1][0], "p2")
        self.assertEqual(ns.params[1][1], "val2")
        ns = opt_parser(["--trace-file", "bla", "-p", "p1", "val1", "-p", "p2", "val2"])
        self.assertIsInstance(ns.params, list)
        self.assertEqual(len(ns.params), 2)
        self.assertEqual(ns.params[0][0], "p1")
        self.assertEqual(ns.params[0][1], "val1")
        self.assertEqual(ns.params[1][0], "p2")
        self.assertEqual(ns.params[1][1], "val2")

    def test_player_class(self):
        try:
            from awstracer.player import TracePlayer
            from awstracer.tracer import Trace
            from awstracer.utils import json_dumps
        except Exception:
            self.fail("cannot import TracePlayer")
        with self.assertRaises(TypeError):
            with TracePlayer():
                pass
        inp = io.StringIO()
        inp.write("[]")
        inp.seek(0)
        with TracePlayer(inp, {}) as tp:
            self.assertEqual(len(tp.traces), 1)

        # check missing arguments
        inp = io.StringIO()
        inp.write("[{}]")
        inp.seek(0)
        with self.assertRaises(ValueError):
            with TracePlayer(inp, {}):
                pass

        t = Trace()
        t.start()
        t.set_input("bla.wut", [])
        t.set_output("reqid", "bla.wut", [])
        t.finish()
        inp = io.StringIO()
        inp.write("{}".format(json_dumps([t.to_dict()])))
        inp.seek(0)
        with TracePlayer(inp) as tp:
            self.assertEqual(len(tp.traces), 2)

        inp.seek(0)
        with TracePlayer(inp, profile="bla-profile", endpoint="bla-endpoint", region="bla-region") as tp:
            self.assertEqual(len(tp.traces), 2)
            out = io.StringIO()
            with redirect_stdout(out):
                tp.play_trace(dryrun=True, sleep_delay=0)
            val = out.getvalue()
            self.assertNotEqual(val.find("--profile bla-profile"), -1)
            self.assertNotEqual(val.find("--endpoint bla-endpoint"), -1)
            self.assertNotEqual(val.find("--region bla-region"), -1)

    def test_player_methods_existence(self):
        try:
            from awstracer.player import TracePlayer
        except Exception:
            self.fail("cannot import TracePlayer")
        methods = ["play_trace", "play_single_trace", "get_shell_poc", "find_connections_between_traces", "find_connections", "prune_connections"]
        for m in methods:
            self.assertIn(m, dir(TracePlayer))

    def test_player_edges(self):
        try:
            from awstracer.player import Edge, MatchingNameAndValueEdge, MatchingNameEdge, MatchingValueEdge
        except Exception:
            self.fail("cannot import TracePlayer")
        self.assertIsInstance(MatchingNameAndValueEdge.__bases__[0], type(Edge))
        self.assertIsInstance(MatchingNameEdge.__bases__[0], type(Edge))
        self.assertIsInstance(MatchingValueEdge.__bases__[0], type(Edge))

    def test_player_play_trace(self):
        try:
            from awstracer.player import TracePlayer
            from awstracer.tracer import Trace
            from awstracer.utils import json_dumps
        except Exception:
            self.fail("cannot import TracePlayer")

        f = io.StringIO()
        with redirect_stdout(f):
            t = Trace()
            t.start()
            t.set_input("bla.wut", {"arg1": "val'\"`ue1"})
            t.set_output("reqid", "bla.wut", [])
            t.finish()
            inp = io.StringIO()
            inp.write("{}".format(json_dumps([t.to_dict()])))
            inp.seek(0)
            with TracePlayer(inp, {}, prompt_color=False) as tp:
                tp.play_trace(dryrun=True, stop_on_error=True, sleep_delay=0)
        self.assertNotEqual(f.getvalue().find("(play) aws bla wut"), -1)
        self.assertNotEqual(f.getvalue().find("--arg1 'val'\"'\"'\"`ue1'"), -1)

    def test_player_find_and_prune_connections(self):
        try:
            from awstracer.player import TracePlayer
            from awstracer.tracer import Trace
            from awstracer.utils import json_dumps
            from awstracer.player import MatchingNameAndValueEdge, MatchingNameEdge, MatchingValueEdge
        except Exception:
            self.fail("cannot import TracePlayer")

        f = io.StringIO()
        with redirect_stdout(f):
            t = Trace()
            t.start()
            t.set_input("bla.wut", {"arg1": "val'\"`ue1"})
            t.set_output("reqid2", "bla.wut", {"ret1": "val1"})
            t.finish()
            t2 = Trace()
            t2.start()
            t2.set_input("bla.wut2", {"ret1": "val1"})
            t2.set_output("reqid2", "bla.wut2", {})
            t2.finish()
            t3 = Trace()
            t3.start()
            t3.set_input("bla.wut3", {"other-param-same-val": "val1"})
            t3.set_output("reqid3", "bla.wut3", {"output-value": "val1"})
            t3.finish()
            t4 = Trace()
            t4.start()
            t4.set_input("bla.wut4", {"output-value": "val2"})
            t4.set_output("reqid4", "bla.wut4", {})
            t4.finish()
            tt = [t, t2, t3, t4]
            inp = io.StringIO()
            inp.write("{}".format(json_dumps([x.to_dict() for x in tt])))
            inp.seek(0)
            with TracePlayer(inp, {}, prompt_color=False) as tp:
                tp.find_connections()
                self.assertEqual(len(tp.connections), 3)

                # test the first connection matching name+value
                c = tp.connections[0]
                self.assertIsInstance(c, MatchingNameAndValueEdge)
                self.assertEqual(c.trace_from.fn_name, "bla.wut")
                self.assertEqual(c.trace_to.fn_name, "bla.wut2")
                self.assertIn("ret1", c.trace_from.outparams)
                self.assertEqual(c.trace_from.outparams["ret1"], "val1")
                self.assertIn("ret1", c.trace_to.inparams)
                self.assertEqual(c.trace_to.inparams["ret1"], "val1")

                # test second connection which should be matching value only
                c = tp.connections[1]
                self.assertIsInstance(c, MatchingValueEdge)
                self.assertEqual(c.trace_from.fn_name, "bla.wut")
                self.assertEqual(c.trace_to.fn_name, "bla.wut3")
                self.assertIn("other-param-same-val", c.trace_to.inparams)
                self.assertEqual(c.trace_to.inparams["other-param-same-val"], "val1")
                self.assertIn("ret1", c.trace_from.outparams)
                self.assertEqual(c.trace_from.outparams["ret1"], "val1")

                # test third connection which should be matching name only
                c = tp.connections[2]
                self.assertIsInstance(c, MatchingNameEdge)
                self.assertEqual(c.trace_from.fn_name, "bla.wut3")
                self.assertEqual(c.trace_to.fn_name, "bla.wut4")
                self.assertIn("output-value", c.trace_from.outparams)
                self.assertEqual(c.trace_from.outparams["output-value"], "val1")
                self.assertIn("output-value", c.trace_to.inparams)
                self.assertEqual(c.trace_to.inparams["output-value"], "val2")

                # test pruning
                tp.prune_connections()
                self.assertEqual(len(tp.connections), 3)

                # add another one that will be pruned
                t5 = Trace()
                t5.start()
                t5.set_input("bla.wut5", {"ret1": "val1"})
                t5.set_output("reqid5", "bla.wut5", {})
                t5.finish()
                tp.traces.append(t5)

                tp.find_connections()
                self.assertEqual(len(tp.connections), 5)
                c = tp.connections[-1]
                self.assertEqual(c.trace_from.fn_name, "bla.wut3")
                tp.prune_connections()
                self.assertEqual(len(tp.connections), 4)
                c = tp.connections[-1]
                self.assertEqual(c.trace_from.fn_name, "bla.wut")
