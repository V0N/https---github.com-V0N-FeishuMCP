import unittest

from app.utils.command_parser import ParsedCommand, parse_command


class TestParseCommand(unittest.TestCase):

    def test_query_one_with_time(self):
        result = parse_command("查 张三 上月")
        self.assertEqual(result.type, "query_one")
        self.assertEqual(result.names, ["张三"])
        self.assertEqual(result.time_text, "上月")

    def test_query_one_no_time(self):
        result = parse_command("查 李四")
        self.assertEqual(result.type, "query_one")
        self.assertEqual(result.names, ["李四"])
        self.assertEqual(result.time_text, "")

    def test_query_self_with_time(self):
        result = parse_command("查我 Q1")
        self.assertEqual(result.type, "query_self")
        self.assertEqual(result.names, [])
        self.assertEqual(result.time_text, "Q1")

    def test_query_self_no_time(self):
        result = parse_command("查我")
        self.assertEqual(result.type, "query_self")
        self.assertEqual(result.names, [])
        self.assertEqual(result.time_text, "")

    def test_query_batch(self):
        result = parse_command("批量查 张三,李四,王五 3月")
        self.assertEqual(result.type, "query_batch")
        self.assertEqual(result.names, ["张三", "李四", "王五"])
        self.assertEqual(result.time_text, "3月")

    def test_query_batch_chinese_comma(self):
        result = parse_command("批量查 张三，李四 上月")
        self.assertEqual(result.type, "query_batch")
        self.assertEqual(result.names, ["张三", "李四"])
        self.assertEqual(result.time_text, "上月")

    def test_select_digit_1(self):
        result = parse_command("1")
        self.assertEqual(result.type, "select")
        self.assertEqual(result.names, ["1"])

    def test_select_digit_2(self):
        result = parse_command("2")
        self.assertEqual(result.type, "select")
        self.assertEqual(result.names, ["2"])

    def test_export(self):
        result = parse_command("导出")
        self.assertEqual(result.type, "export")

    def test_unknown(self):
        result = parse_command("你好")
        self.assertEqual(result.type, "unknown")

    def test_query_one_with_spaces(self):
        result = parse_command("查  张三  上月")
        self.assertEqual(result.type, "query_one")
        self.assertEqual(result.names, ["张三"])
        self.assertEqual(result.time_text, "上月")


if __name__ == "__main__":
    unittest.main()
