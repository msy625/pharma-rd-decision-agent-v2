import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class MobileEvidenceCenterFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.static_index = STATIC_INDEX.read_text(encoding="utf-8")
        css_start = cls.template.index("[data-app]{transition")
        css_end = cls.template.index("</style>", css_start)
        cls.responsive_css = cls.template[css_start:css_end]
        evidence_start = cls.template.index('<sc-if value="{{ isEvidence }}">')
        evidence_end = cls.template.index('<sc-if value="{{ isDatabase }}">', evidence_start)
        cls.evidence_template = cls.template[evidence_start:evidence_end]

    def test_mobile_breakpoints_cover_requested_widths(self):
        self.assertIn("@media(max-width:640px)", self.responsive_css)
        self.assertIn("@media(max-width:420px)", self.responsive_css)
        self.assertIn("[data-content]{padding:16px 14px 44px !important}", self.responsive_css)

    def test_all_three_evidence_tabs_have_mobile_layout_hooks(self):
        for hook in [
            'data-evidence=""',
            'data-evidence-chain=""',
            'data-evidence-company-compare=""',
        ]:
            self.assertIn(hook, self.evidence_template)
        self.assertIn(
            "[data-cols],[data-chat],[data-research],[data-evidence]{grid-template-columns:minmax(0,1fr) !important}",
            self.responsive_css,
        )
        self.assertIn(
            "@media(max-width:900px){\n  [data-evidence-chain],[data-evidence-company-compare]{grid-template-columns:minmax(0,1fr) !important}",
            self.responsive_css,
        )

    def test_desktop_layout_contract_is_preserved(self):
        self.assertIn(
            'data-evidence="" style="display:grid;grid-template-columns:minmax(0,1fr) 420px',
            self.evidence_template,
        )
        self.assertIn(
            'data-evidence-chain="" style="display:grid;grid-template-columns:minmax(0,1fr) 460px',
            self.evidence_template,
        )
        self.assertIn(
            'data-evidence-company-compare="" style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr))',
            self.evidence_template,
        )
        responsive_1080 = self.responsive_css[
            self.responsive_css.index("@media(max-width:1080px)") : self.responsive_css.index("@media(max-width:900px)")
        ]
        self.assertNotIn("data-evidence-chain", responsive_1080)
        self.assertNotIn("data-evidence-company-compare", responsive_1080)

    def test_mobile_cards_use_full_width_and_zero_min_width(self):
        self.assertIn(
            "[data-evidence-card]{width:100%;min-width:0;max-width:100%",
            self.responsive_css,
        )
        for hook in [
            'data-evidence-page=""',
            'data-evidence-card=""',
            'data-evidence-detail=""',
            'data-evidence-chain-detail=""',
            'data-evidence-company-card=""',
        ]:
            self.assertIn(hook, self.evidence_template)

    def test_mobile_card_and_detail_fields_switch_to_one_column(self):
        for hook in [
            'data-evidence-card-fields=""',
            'data-evidence-detail-fields=""',
            'data-evidence-item-fields=""',
            'data-evidence-compact-grid=""',
        ]:
            self.assertIn(hook, self.evidence_template)
        self.assertIn(
            "[data-evidence-card-fields],[data-evidence-detail-fields],[data-evidence-item-fields],[data-evidence-compact-grid]{grid-template-columns:minmax(0,1fr) !important}",
            self.responsive_css,
        )

    def test_long_values_and_labels_can_wrap_without_page_scroll(self):
        self.assertIn(
            "[data-evidence-page]{overflow-wrap:anywhere;word-break:normal}",
            self.responsive_css,
        )
        self.assertIn("[data-evidence-card-head]{align-items:flex-start !important;flex-wrap:wrap}", self.responsive_css)
        self.assertNotIn("overflow-x:auto", self.responsive_css)

    def test_mobile_controls_and_header_have_non_collapsing_layout(self):
        for hook in [
            'data-header=""',
            'data-breadcrumb=""',
            'data-evidence-center-tabs=""',
            'data-evidence-query-controls=""',
            'data-evidence-toolbar=""',
        ]:
            self.assertIn(hook, self.template)
        self.assertIn("[data-header]>button{flex:none}", self.responsive_css)
        self.assertIn("[data-evidence-center-tabs]>button{flex:1 1 calc(50% - 4px)", self.responsive_css)
        self.assertIn("[data-evidence-toolbar]>button{width:100%}", self.responsive_css)

    def test_360_and_390_metrics_become_single_column(self):
        self.assertIn(
            "@media(max-width:420px){\n  [data-evidence-metrics]{grid-template-columns:minmax(0,1fr) !important}",
            self.responsive_css,
        )
        self.assertGreaterEqual(self.evidence_template.count('data-evidence-metrics=""'), 2)

    def test_static_index_is_generated_from_current_sources(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(self.static_index, expected)


if __name__ == "__main__":
    unittest.main()
