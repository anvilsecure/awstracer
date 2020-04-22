import io
import tempfile
import unittest
import uuid
from datetime import datetime


class TestTracerUtils(unittest.TestCase):

    def test_datetime_json(self):
        try:
            from awstracer.utils import json_loads, json_load, json_dumps
        except Exception:
            self.fail("json_load(s), json_dump(s) import failed")
        val = {"_": datetime.now()}
        ret1 = json_dumps(val)
        self.assertNotEqual(ret1.find("_isoformat"), -1)
        ret2 = json_loads(ret1.encode("utf-8"))
        self.assertEqual(val, ret2)
        self.assertEqual(val, json_load(io.StringIO(ret1)))

    def test_camelcase_conversion(self):
        try:
            from awstracer.utils import convert_from_camelcase, convert_to_camelcase
        except Exception:
            self.fail("camelcase imports failed")

        test = "ExecutePartiQLStatement"
        ret1 = convert_from_camelcase(test)
        self.assertEqual("execute-parti-ql-statement", ret1)
        ret2 = convert_to_camelcase(ret1)

        # can't reliably convert this back
        self.assertNotEqual(test, ret2)

        test = "BlaBlaBla"
        ret1 = convert_from_camelcase(test)
        self.assertEqual("bla-bla-bla", ret1)
        ret2 = convert_to_camelcase(ret1)
        self.assertEqual(test, ret2)

    def test_process_file_argument(self):
        try:
            from awstracer.utils import process_file_argument
        except Exception:
            self.fail("process_file_argument failed")

        self.assertEqual(process_file_argument("bla"), "bla")
        # check non-existing file
        self.assertIsNone(process_file_argument("file://{}".format(uuid.uuid4().hex)))
        # test actual reading from file
        tp = tempfile.NamedTemporaryFile()
        tp.write(b"hello w0rld")
        tp.seek(0)
        arg = process_file_argument("file://{}".format(tp.name))
        self.assertEqual(arg, "hello w0rld")
