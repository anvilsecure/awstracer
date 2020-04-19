import unittest


class TestTracerUtils(unittest.TestCase):

    def test_datetime_json(self):
        try:
            from awstracer.utils import json_loads, json_load, json_dumps
        except Exception:
            self.fail("json_load(s), json_dump(s) import failed")
        from datetime import datetime
        import io
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
