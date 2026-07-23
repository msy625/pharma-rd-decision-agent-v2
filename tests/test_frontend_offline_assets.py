import hashlib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from tests.test_deployment_health import _ASGIClient
from webapp import main as webapp_main


STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"
STATIC_RUNTIME = ROOT / "webapp" / "static" / "dc-runtime.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
MANIFEST = ROOT / "webapp" / "static" / "vendor" / "manifest.json"
SOURCE_REGISTRY = ROOT / "data" / "source_registry.csv"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _local_static_paths(html: str) -> set[str]:
    paths = set()
    for pattern in [
        r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']",
        r"<link\b[^>]*\bhref=[\"']([^\"']+)[\"']",
    ]:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE):
            value = match.group(1)
            if value.startswith("/static/"):
                paths.add(value)
    return paths


class FrontendOfflineAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = _read(STATIC_INDEX)
        cls.runtime = _read(STATIC_RUNTIME)
        cls.template = _read(TEMPLATE)
        cls.component = _read(COMPONENT)
        cls.manifest = json.loads(_read(MANIFEST))
        cls.client = _ASGIClient(webapp_main.app)

    def test_01_key_runtime_no_longer_references_public_cdn(self):
        key_runtime = self.index + "\n" + self.runtime + "\n" + self.template
        for forbidden in [
            "unpkg.com",
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "fonts.googleapis.com",
            "fonts.gstatic.com",
        ]:
            self.assertNotIn(forbidden, key_runtime)

    def test_02_local_script_and_link_resources_exist(self):
        for url_path in _local_static_paths(self.index):
            local_path = ROOT / "webapp" / url_path.lstrip("/")
            self.assertTrue(local_path.exists(), url_path)

    def test_03_react_versions_are_explicit_and_consistent(self):
        by_name = {item["name"]: item for item in self.manifest["resources"]}
        self.assertEqual(by_name["react"]["version"], "18.3.1")
        self.assertEqual(by_name["react-dom"]["version"], "18.3.1")
        self.assertIn("18.3.1", by_name["react"]["file"])
        self.assertIn("18.3.1", by_name["react-dom"]["file"])
        self.assertIn("7.26.4", by_name["babel-standalone"]["file"])

    def test_04_vendor_files_are_not_empty_or_html_error_pages(self):
        checks = {
            "react": (5_000, "React"),
            "react-dom": (100_000, "ReactDOM"),
            "babel-standalone": (1_000_000, "Babel"),
        }
        for item in self.manifest["resources"]:
            path = ROOT / "webapp" / item["file"].lstrip("/")
            content = path.read_text(encoding="utf-8", errors="replace")
            min_size, marker = checks[item["name"]]
            self.assertGreater(path.stat().st_size, min_size, item["file"])
            self.assertFalse(content.lstrip().lower().startswith("<!doctype html"), item["file"])
            self.assertIn(marker, content, item["file"])

    def test_05_vendor_license_files_exist(self):
        for item in self.manifest["resources"]:
            license_path = ROOT / "webapp" / item["license_file"].lstrip("/")
            self.assertTrue(license_path.exists(), item["license_file"])
            self.assertIn("MIT", license_path.read_text(encoding="utf-8", errors="replace"))

    def test_06_manifest_sha256_matches_files(self):
        for item in self.manifest["resources"]:
            path = ROOT / "webapp" / item["file"].lstrip("/")
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(_sha256(path), item["sha256"], item["file"])

    def test_07_fastapi_serves_vendor_resources(self):
        for item in self.manifest["resources"]:
            response = self.client.get(item["file"])
            self.assertEqual(response.status_code, 200, item["file"])
            self.assertGreater(len(response.content), 5_000, item["file"])

    def test_08_vendor_content_type_is_reasonable(self):
        for item in self.manifest["resources"]:
            response = self.client.get(item["file"])
            content_type = response.headers.get("content-type", "")
            self.assertRegex(content_type, r"(javascript|text/plain|octet-stream)", item["file"])
            text = response.text[:200]
            self.assertNotIn("<html", text.lower(), item["file"])
            self.assertTrue(
                text.lstrip().startswith(("/*", "!", "(function", "var ", "(()=>", "/**")),
                item["file"],
            )

    def test_09_homepage_still_contains_main_navigation(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200, response.text[:200])
        for label in ["工作台", "智能问答", "公司画像", "研发证据查询", "白盒溯源"]:
            self.assertIn(label, response.text)

    def test_10_evidence_tabs_still_exist(self):
        for label in ["来源检索", "证据链", "企业对比", "循证问答"]:
            self.assertIn(label, self.index)
            self.assertIn(label, self.template)

    def test_11_source_urls_are_not_rewritten_to_local_static_paths(self):
        registry_text = _read(SOURCE_REGISTRY)
        self.assertIn("https://clinicaltrials.gov/study/NCT03663205", registry_text)
        self.assertIn("https://pubmed.ncbi.nlm.nih.gov/39608979/", registry_text)
        self.assertNotIn("/static/clinicaltrials", registry_text.lower())
        self.assertNotIn("/static/pubmed", registry_text.lower())
        self.assertIn("source_url", self.index)
        self.assertIn("target=\"_blank\"", self.index)

    def test_12_new_frontend_asset_code_has_no_secret_or_personal_path(self):
        checked = [
            STATIC_RUNTIME,
            MANIFEST,
            ROOT / "webapp" / "static" / "vendor" / "react" / "react.production.min-18.3.1.js",
            ROOT / "webapp" / "static" / "vendor" / "react-dom" / "react-dom.production.min-18.3.1.js",
            ROOT / "webapp" / "static" / "vendor" / "babel" / "babel.min-7.26.4.js",
        ]
        for path in checked:
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotRegex(text, r"sk-[A-Za-z0-9_-]{12,}", str(path))
            forbidden_paths = ["/" + "home" + "/", "/" + "root" + "/", "C:" + "\\", "\\" + "Users" + "\\"]
            for forbidden in forbidden_paths:
                self.assertNotIn(forbidden, text, str(path))

    def test_13_static_index_is_in_sync_with_frontend_source(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(expected, self.index)

    def test_14_runtime_loads_react_from_local_vendor_paths(self):
        for expected in [
            "/static/vendor/react/react.production.min-18.3.1.js",
            "/static/vendor/react-dom/react-dom.production.min-18.3.1.js",
            "/static/vendor/babel/babel.min-7.26.4.js",
        ]:
            self.assertIn(expected, self.runtime)


if __name__ == "__main__":
    unittest.main()
