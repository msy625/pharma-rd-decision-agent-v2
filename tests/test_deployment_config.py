import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_REQUIREMENTS = ROOT / "requirements-deploy.txt"
PYTHON_VERSION = ROOT / ".python-version"
RENDER_YAML = ROOT / "render.yaml"


def _requirement_names() -> set[str]:
    names = set()
    for raw_line in DEPLOY_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip().lower()
        names.add(name)
    return names


def _render_text() -> str:
    return RENDER_YAML.read_text(encoding="utf-8")


class DeploymentConfigTest(unittest.TestCase):
    def test_01_deploy_requirements_exists(self):
        self.assertTrue(DEPLOY_REQUIREMENTS.exists())

    def test_02_deploy_requirements_exclude_old_heavy_dependencies(self):
        forbidden = {
            "streamlit",
            "pandas",
            "chromadb",
            "sentence-transformers",
            "sentence_transformers",
            "torch",
            "langchain",
            "pdfplumber",
            "openpyxl",
            "streamlit-echarts",
        }
        self.assertTrue(forbidden.isdisjoint(_requirement_names()))

    def test_03_deploy_requirements_include_core_direct_dependencies(self):
        self.assertEqual(
            _requirement_names(),
            {"fastapi", "uvicorn", "pydantic", "openai"},
        )

    def test_04_python_version_is_full_patch_version(self):
        version = PYTHON_VERSION.read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^3\.12\.\d+$")

    def test_05_render_yaml_is_parseable_when_yaml_available(self):
        text = _render_text()
        try:
            import yaml
        except ImportError:
            self.assertIn("services:", text)
            self.assertIn("type: web", text)
            return
        parsed = yaml.safe_load(text)
        self.assertIsInstance(parsed, dict)
        self.assertIsInstance(parsed.get("services"), list)
        self.assertEqual(parsed["services"][0]["type"], "web")

    def test_06_render_build_uses_deploy_requirements(self):
        self.assertIn("buildCommand: pip install -r requirements-deploy.txt", _render_text())

    def test_07_render_start_uses_app_host_and_port(self):
        text = _render_text()
        self.assertIn("python -m uvicorn webapp.main:app", text)
        self.assertIn("--host 0.0.0.0", text)
        self.assertIn("--port $PORT", text)

    def test_08_render_health_check_path(self):
        self.assertIn("healthCheckPath: /health", _render_text())

    def test_09_render_preview_plan_is_explicit(self):
        text = _render_text()
        self.assertIn("plan: free", text)
        self.assertIn("region: singapore", text)
        self.assertIn("autoDeploy: false", text)

    def test_10_render_grounded_qa_llm_is_disabled_by_default(self):
        text = _render_text()
        self.assertIn("key: GROUNDED_QA_LLM_ENABLED", text)
        self.assertIn('value: "false"', text)

    def test_11_render_yaml_does_not_contain_real_secret(self):
        text = _render_text()
        self.assertIn("sync: false", text)
        self.assertNotRegex(text, r"sk-[A-Za-z0-9_-]{12,}")
        self.assertNotRegex(text, r"DEEPSEEK_API_KEY:\s*['\"]?[A-Za-z0-9_-]{12,}")

    def test_12_env_is_still_git_ignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "-v", ".env"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn(".gitignore", result.stdout)

    def test_13_render_yaml_does_not_reference_legacy_data_paths(self):
        text = _render_text()
        for forbidden in ["enterprise_analysis.db", "data/chroma", "CHROMA", "sqlite", "demo_cache"]:
            self.assertNotIn(forbidden, text)

    def test_14_render_yaml_has_no_personal_absolute_paths(self):
        text = _render_text()
        forbidden_paths = ["/" + "home" + "/", "/" + "root" + "/", "C:" + "\\", "\\" + "Users" + "\\"]
        for forbidden in forbidden_paths:
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
