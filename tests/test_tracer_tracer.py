import unittest


class TestTracer(unittest.TestCase):

    def setUp(self):
        try:
            from awstracer.tracer import Trace
        except Exception:
            self.fail("Trace import failed")
        try:
            t = Trace()
        except Exception:
            self.fail("Trace construction failed")
        self.t = t

    def test_trace_attrs(self):
        attrs = ("request_id", "fn_name", "inparams", "outparams", "ts_start", "ts_end")
        t = self.t
        for attr in attrs:
            self.assertIn(attr, dir(t))
        self.assertEqual(t.ts_start, None)
        self.assertEqual(t.ts_end, None)
        self.assertIsInstance(t.request_id, str)
        self.assertIsInstance(t.fn_name, str)
        self.assertIsInstance(t.inparams, dict)
        self.assertIsInstance(t.outparams, dict)

    def test_trace_start_finish(self):
        t = self.t
        for attr in ("start", "finish"):
            self.assertIn(attr, dir(t))
        t.start()
        import time
        time.sleep(.01)
        t.finish()
        diff = t.ts_end - t.ts_start
        self.assertEqual(diff.seconds, 0)
        self.assertGreaterEqual(diff.microseconds, 10)

    def test_trace_set_inputs(self):
        t = self.t
        for attr in ("set_input", "set_output"):
            self.assertIn(attr, dir(t))
        t.set_input("bla", {"wut": "bla"})
        self.assertEqual(t.fn_name, "bla")
        self.assertIn("wut", t.inparams)
        self.assertEqual(t.inparams["wut"], "bla")

        # test for different fn_name for output values
        with self.assertRaises(ValueError):
            t.set_output("blaaaaaal", "", {})
        t.set_output("reqid", "bla", {"wot": "bluh"})
        self.assertEqual(t.fn_name, "bla")
        self.assertEqual(t.request_id, "reqid")
        self.assertIn("wot", t.outparams)
        self.assertEqual(t.outparams["wot"], "bluh")

    def test_trace_tofrom_dicts(self):
        from awstracer.tracer import Trace
        t = self.t
        for attr in ("to_dict", "from_dict"):
            self.assertIn(attr, dir(t))
        d = t.to_dict()
        for n in ("request_id", "fn_name", "inparams", "outparams", "ts_start", "ts_end"):
            self.assertIn(n, d)
            self.assertEqual(d[n], getattr(t, n))
        t2 = Trace.from_dict(d)
        for n in ("request_id", "fn_name", "inparams", "outparams", "ts_start", "ts_end"):
            self.assertIn(n, dir(t2))
            self.assertEqual(getattr(t, n), getattr(t2, n))

    def test_trace_get_shell(self):
        from awstracer.tracer import Trace
        t = Trace()
        t.set_input("bla", {"wut": "wot"})
        for attr in ("get_shell_poc", "get_shell_var"):
            self.assertIn(attr, dir(t))
        with self.assertRaises(ValueError):
            # fn name is not correct
            t.get_shell_poc({})
        t.set_input("bla.blu", {"wut": "wot", "hi": "`\"escape'"})
        r = t.get_shell_poc()
        self.assertTrue(r.startswith("aws"))
        r = r.split(" ")
        self.assertEqual(len(r), 7)
        self.assertEqual(r[1], "bla")
        self.assertEqual(r[2], "blu")
        self.assertEqual(r[3], "--wut")
        self.assertEqual(r[4], "wot")
        self.assertEqual(r[5], "--hi")
        self.assertEqual(r[6], '\'`"escape\'"\'"\'\'')

        r = t.get_shell_var("BLA", "wut")
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0], "--bl-a")
        self.assertEqual(r[1], "wut")

        r = t.get_shell_var("hi", "`\"arg{};'")
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0], "--hi")
        self.assertEqual(r[1], "\'`\"arg{};\'\"\'\"\'\'")

    def test_event_capturer(self):
        try:
            from awstracer.tracer import EventCapturer
        except Exception:
            self.fail("error while importing eventcapturer")
        ev = EventCapturer()
        self.assertIn("trace", dir(ev))
        self.assertIn("events_captured", dir(ev))
        self.assertIn("emit", dir(ev))

        ev.emit("bla")
        self.assertIn("bla", ev.events_captured)
        with self.assertRaises(Exception):
            ev.emit("provide-client-params", **{})
            ev.emit("provide-client-params", **{"params": {}})
            ev.emit("provide-client-params.", **{"params": {}})
        ev.emit("provide-client-params.x", **{"params": {}})
        self.assertEqual(ev.trace.fn_name, "x")
        ev.emit("provide-client-params.xy", **{"params": {"test": "123"}})
        self.assertEqual(ev.trace.fn_name, "xy")
        self.assertIn("test", ev.trace.inparams)
        self.assertEqual(ev.trace.inparams["test"], "123")

        with self.assertRaises(Exception):
            ev.emit("after-call", **{})
            ev.emit("after-call.", **{})
            ev.emit("after-call.asdfx", **{"parsed": {}})
            ev.emit("after-call.asdfx", **{"parsed": {"ResponseMetadata": {}}})
            ev.emit("after-call.asdfx", **{"parsed": {"ResponseMetadata": {"RequestId": "req123"}}})

        # reset input parameters too to make them match
        ev.emit("provide-client-params.asdfx", **{"params": {}})
        ev.emit("after-call.asdfx", **{"parsed": {"ResponseMetadata": {"RequestId": "req123"}, "tro": "lll"}})
        self.assertEqual(ev.trace.fn_name, "asdfx")
        self.assertEqual(ev.trace.request_id, "req123")
        self.assertEqual(len(ev.trace.outparams), 1)
        self.assertIn("tro", ev.trace.outparams)
        self.assertEqual(ev.trace.outparams["tro"], "lll")

    def test_tracerunner(self):
        try:
            from awstracer.tracer import TraceRunner
            from awstracer.tracer import EventCapturer
        except Exception:
            self.fail("import failed for tracerunner")
        try:
            import awscli
        except Exception:
            self.fail("awscli import failed")

        self.assertIn("EnvironmentVariables", dir(awscli))
        self.assertIn("clidriver", dir(awscli))

        # establish that all the internals of AWS CLI haven't changed
        # such that the tracer _create_clidriver() most likely still
        # works
        try:
            import awscli.plugin
        except Exception:
            self.fail("awscli.plugin import failed")
        self.assertIn("load_plugins", dir(awscli.plugin))
        self.assertIn("CLIDriver", dir(awscli.clidriver))
        self.assertIn("_set_user_agent_for_session", dir(awscli.clidriver))

        try:
            import botocore
            import botocore.hooks
        except Exception:
            self.fail("botocore/botocore.hooks import failed")

        self.assertIn("session", dir(botocore))
        self.assertIn("Session", dir(botocore.session))

        s = botocore.session.Session(awscli.EnvironmentVariables)
        self.assertIn("register_component", dir(s))
        tr = TraceRunner()
        ev = EventCapturer()
        self.assertIn("run_aws_cmd", dir(tr))
        self.assertIn("_create_clidriver", dir(tr))

        # redirect stdout and stderr as the AWS CLI output is annoying and not necessary
        from contextlib import redirect_stderr, redirect_stdout
        import io
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()):
                with redirect_stderr(io.StringIO()):
                    tr.run_aws_cmd(["definitelynotexistingcommand"])
                    tr.run_aws_cmd(["s3", "definitelynotexistingcommand"])

        ret = tr._create_clidriver(ev)
        self.assertIsNotNone(ret)
        self.assertIsInstance(ret, awscli.clidriver.CLIDriver)
