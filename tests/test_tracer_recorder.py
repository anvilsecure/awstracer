import io
import tempfile
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout


class TestRecorder(unittest.TestCase):
    def test_options(self):
        try:
            from awstracer.recorder import opt_parser
        except Exception:
            self.fail("cannot import opt_parser")
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()):
                with redirect_stderr(io.StringIO()):
                    opt_parser([])
        ns = opt_parser(["--trace-file", "bla"])
        opts = ("prompt_color", "prompt_on_misc", "prompt_on_save", "enable_misc_cmd", "trace_file")
        for opt in opts:
            self.assertIn(opt, ns)
        self.assertEqual(ns.trace_file, "bla")
        # check default settings for options
        self.assertTrue(ns.prompt_color)
        self.assertTrue(ns.prompt_on_save)
        self.assertTrue(ns.prompt_on_misc)
        self.assertFalse(ns.enable_misc_cmd)
        ns = opt_parser(["--trace-file", "bla", "-c", "-n", "-s", "-d"])
        self.assertFalse(ns.prompt_color)
        self.assertFalse(ns.prompt_on_save)
        self.assertFalse(ns.prompt_on_misc)
        self.assertTrue(ns.enable_misc_cmd)

    def test_recorder_class(self):
        try:
            from awstracer.recorder import TraceRecorder
            from awstracer.tracer import TraceRunner
        except Exception:
            self.fail("cannot import TraceRecorder")
        with self.assertRaises(TypeError):
            tr = TraceRecorder()
        # give random filename
        tr = TraceRecorder(uuid.uuid4().hex)
        # prompt on save should be on by default
        self.assertIsInstance(tr, TraceRunner)
        self.assertTrue(tr.prompt_on_save)
        self.assertIn("run_aws_cmd", dir(tr))

    def test_recorder_file_arguments(self):
        try:
            from awstracer.recorder import TraceRecorder
        except Exception:
            self.fail("cannot import TraceRecorder")
        out = io.StringIO()
        with redirect_stdout(out):
            tr = TraceRecorder(uuid.uuid4().hex)
            tmp_fn = "/tmp/{}".format(uuid.uuid4().hex)
            tr.run_aws_cmd(["aws", "bla", "bla", "file://{}".format(tmp_fn)])
            # check for error message which should contain the file we can't read
            self.assertNotEqual(out.getvalue().find(tmp_fn), -1)

        # test actual reading from file
        tp = tempfile.NamedTemporaryFile()
        tp.write(b"hello w0rld")
        tp.seek(0)
        tr = TraceRecorder(uuid.uuid4().hex)
        args = tr.process_file_arguments(["aws", "bla", "bla", "file://{}".format(tp.name)])
        self.assertEqual(len(args), 4)
        self.assertEqual(args[3], "hello w0rld")
