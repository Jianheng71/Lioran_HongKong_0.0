from io import BytesIO
import unittest
from app.cleaner import clean_html, clean_value, has_main_content, is_login_or_paywall
from app.exporter import export_xlsx
from app.models import ScrapeTask
from app.local_llm import normalize_schema, parse_model_json
from openpyxl import load_workbook


class DetailPageTests(unittest.TestCase):
    def test_relative_link_becomes_absolute(self):
        self.assertEqual(
            clean_value("/policy/42", "https://example.com/news/", "attr:href"),
            "https://example.com/policy/42",
        )

    def test_date_text_is_preserved(self):
        original = "2026年11月10日 09:30"
        self.assertEqual(clean_value(original, "https://example.com", "text"), original)

    def test_javascript_links_are_not_exported_as_web_links(self):
        self.assertEqual(
            clean_value("javascript:alert(1)", "https://example.com", "attr:href"),
            "",
        )

    def test_empty_login_gate_is_detected(self):
        html = clean_html(
            "<nav>site navigation</nav><main><p>Sign in to continue</p></main>"
        )
        self.assertFalse(has_main_content(html))
        self.assertTrue(is_login_or_paywall(html, has_main_content(html)))

    def test_crawl4ai_attribute_field_is_normalized(self):
        schema = normalize_schema(
            {
                "baseSelector": "article",
                "fields": [
                    {
                        "name": "link",
                        "selector": "a",
                        "type": "attribute",
                        "attribute": "href",
                    }
                ],
            }
        )
        self.assertEqual(schema["base_selector"], "article")
        self.assertEqual(schema["fields"][0]["type"], "attr:href")

    def test_hermes_tool_call_json_is_parsed(self):
        response = '<tool_call>{"base_selector": "article", "fields": []}</tool_call>'
        self.assertEqual(
            parse_model_json(response),
            {"base_selector": "article", "fields": []},
        )

    def test_excel_export_sets_requested_column_widths(self):
        task = ScrapeTask(
            url="https://example.test/",
            requirement="test",
            columns=["序号", "标题", "链接", "栏目名称", "类别"],
            rows=[["1", "Title", "https://example.test/item", "News", "新闻"]],
            schema={},
        )
        workbook = load_workbook(BytesIO(export_xlsx(task).getvalue()))
        sheet = workbook["Lioran"]
        self.assertEqual(
            [sheet.column_dimensions[column].width for column in "ABCDE"],
            [8, 60, 80, 15, 15],
        )


if __name__ == "__main__":
    unittest.main()
