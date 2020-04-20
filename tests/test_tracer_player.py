import unittest


class TestPlayer(unittest.TestCase):
    def test_options(self):
        try:
            from awstracer.player import opt_parser
        except Exception:
            self.fail("cannot import opt_parser")
        from contextlib import redirect_stderr, redirect_stdout
        import io
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
