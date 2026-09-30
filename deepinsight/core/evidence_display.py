"""Shared display categories for the website evidence library.

The normalized tables preserve detailed upstream source types.  The website
uses these three stable user-facing groups so that a registry record, a paper,
and a regulatory/company document are never mixed into one ambiguous list.
"""

from __future__ import annotations


DISPLAY_CATEGORIES = {
    "clinical_trial": "临床试验",
    "publication": "论文证据",
    "regulatory_company": "监管与公司资料",
}

_TYPE_TO_CATEGORY = {
    "CLINICAL_TRIAL_REGISTRY": "clinical_trial",
    "TRIAL_REGISTRY": "clinical_trial",
    "COMPANY_TRIAL_PAGE": "clinical_trial",
    "PUBMED_ARTICLE": "publication",
    "PEER_REVIEWED_PUBLICATION": "publication",
    "REGULATORY_PRIMARY": "regulatory_company",
    "COMPANY_FORMAL_DISCLOSURE": "regulatory_company",
    "COMPANY_PIPELINE": "regulatory_company",
}


def display_category(source_type: object) -> str:
    """Classify a detailed normalized source type into one display group."""
    return _TYPE_TO_CATEGORY.get(str(source_type or "").strip(), "regulatory_company")


def display_category_label(source_type: object) -> str:
    return DISPLAY_CATEGORIES[display_category(source_type)]
