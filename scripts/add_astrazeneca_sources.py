#!/usr/bin/env python3
"""Idempotently add the verified AstraZeneca NSCLC supplement to the registry."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "source_registry.csv"
VERIFIED_AT = "2026-07-23"


TRIALS = [
    {
        "source_id": "A001",
        "registry_id": "NCT02296125",
        "study_name": "FLAURA",
        "original_title": "AZD9291 Versus Gefitinib or Erlotinib in Patients With Locally Advanced or Metastatic Non-small Cell Lung Cancer",
        "normalized_title_zh": "FLAURA：奥希替尼对比吉非替尼或厄洛替尼一线治疗 EGFR 突变晚期 NSCLC",
        "population": "既往未接受系统治疗的 EGFR 突变局部晚期或转移性 NSCLC",
        "intervention": "奥希替尼（AZD9291）",
        "comparator": "吉非替尼或厄洛替尼",
        "drug_names": "奥希替尼;Osimertinib;AZD9291;吉非替尼;Gefitinib;厄洛替尼;Erlotinib",
        "study_status": "Completed",
        "source_last_updated": "2025-11-20",
    },
    {
        "source_id": "A003",
        "registry_id": "NCT02511106",
        "study_name": "ADAURA",
        "original_title": "AZD9291 Versus Placebo in Patients With Stage IB-IIIA Non-small Cell Lung Carcinoma, Following Complete Tumour Resection With or Without Adjuvant Chemotherapy",
        "normalized_title_zh": "ADAURA：完全切除后 EGFR 突变 IB-IIIA 期 NSCLC 的奥希替尼辅助治疗研究",
        "population": "完全切除后的 EGFR 突变 IB-IIIA 期 NSCLC",
        "intervention": "奥希替尼（AZD9291）",
        "comparator": "安慰剂",
        "drug_names": "奥希替尼;Osimertinib;AZD9291",
        "study_status": "Active, not recruiting",
        "source_last_updated": "2025-06-30",
    },
    {
        "source_id": "A005",
        "registry_id": "NCT03521154",
        "study_name": "LAURA",
        "original_title": "A Global Study to Assess the Effects of Osimertinib Following Chemoradiation in Patients With Stage III Unresectable Non-small Cell Lung Cancer (LAURA)",
        "normalized_title_zh": "LAURA：不可切除 III 期 EGFR 突变 NSCLC 放化疗后奥希替尼研究",
        "population": "放化疗后未进展的不可切除 III 期 EGFR 突变 NSCLC",
        "intervention": "奥希替尼",
        "comparator": "安慰剂",
        "drug_names": "奥希替尼;Osimertinib;AZD9291",
        "study_status": "Active, not recruiting",
        "source_last_updated": "2025-06-30",
    },
    {
        "source_id": "A007",
        "registry_id": "NCT04035486",
        "study_name": "FLAURA2",
        "original_title": "A Study of Osimertinib With or Without Chemotherapy as 1st Line Treatment in Patients With Mutated Epidermal Growth Factor Receptor Non-Small Cell Lung Cancer (FLAURA2)",
        "normalized_title_zh": "FLAURA2：奥希替尼联合或不联合化疗一线治疗 EGFR 突变晚期 NSCLC",
        "population": "既往未接受系统治疗的 EGFR 突变局部晚期或转移性 NSCLC",
        "intervention": "奥希替尼联合培美曲塞及卡铂或顺铂",
        "comparator": "奥希替尼单药",
        "drug_names": "奥希替尼;Osimertinib;AZD9291;培美曲塞;Pemetrexed;卡铂;Carboplatin;顺铂;Cisplatin",
        "study_status": "Active, not recruiting",
        "source_last_updated": "2025-06-30",
    },
]

PUBLICATIONS = [
    ("A002", "NCT02296125", "FLAURA", "31751012", "Overall Survival with Osimertinib in Untreated, EGFR-Mutated Advanced NSCLC.", "2020-01-02", "10.1056/NEJMoa1913662"),
    ("A004", "NCT02511106", "ADAURA", "37272535", "Overall Survival with Osimertinib in Resected EGFR-Mutated NSCLC.", "2023-07-13", "10.1056/NEJMoa2304594"),
    ("A006", "NCT03521154", "LAURA", "38828946", "Osimertinib after Chemoradiotherapy in Stage III EGFR-Mutated NSCLC.", "2024-08-15", "10.1056/NEJMoa2402614"),
    ("A008", "NCT04035486", "FLAURA2", "37937763", "Osimertinib with or without Chemotherapy in EGFR-Mutated Advanced NSCLC.", "2023-11-23", "10.1056/NEJMoa2306434"),
]


def base_row(fieldnames: list[str]) -> dict[str, str]:
    row = {field: "" for field in fieldnames}
    row.update(
        {
            "company": "AstraZeneca",
            "company_cn": "阿斯利康",
            "company_current_name": "AstraZeneca",
            "company_display_name": "阿斯利康（AstraZeneca）",
            "sponsor_original": "AstraZeneca",
            "disease": "非小细胞肺癌（NSCLC）",
            "original_language": "en",
            "verification_status": "已人工核验",
            "verified_at": VERIFIED_AT,
            "study_phase": "Phase 3",
            "biomarker_requirements": "EGFR 突变",
            "drug_names": "奥希替尼;Osimertinib;AZD9291",
            "scope_limitation": "仅代表当前收录的公开 NSCLC 证据样本，不代表企业全部研发管线。",
        }
    )
    return row


def build_rows(fieldnames: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in TRIALS:
        row = base_row(fieldnames)
        row.update(item)
        row.update(
            {
                "source_type": "ClinicalTrials.gov",
                "url": f"https://clinicaltrials.gov/study/{item['registry_id']}",
                "official_study_id": item["registry_id"],
                "notes": "通过 ClinicalTrials.gov v2 官方 API 核验试验编号、申办方、阶段和状态。",
            }
        )
        rows.append(row)
    for source_id, trial_id, study_name, pmid, title, publication_date, doi in PUBLICATIONS:
        row = base_row(fieldnames)
        row.update(
            {
                "source_id": source_id,
                "source_type": "PubMed",
                "original_title": title,
                "original_title_en": title,
                "normalized_title_zh": f"{study_name} 主要结果论文：{title}",
                "study_name": study_name,
                "population": "EGFR 突变 NSCLC 研究人群；具体分期与治疗场景以原文为准",
                "intervention": "奥希替尼",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "publication_date": publication_date,
                "parent_trial_id": trial_id,
                "pmid": pmid,
                "publication_type": "期刊论文",
                "analysis_stage": "主要分析或总生存分析",
                "evidence_version": "当前收录版本",
                "is_latest_evidence": "true",
                "journal": "New England Journal of Medicine",
                "doi": doi,
                "evidence_relation": f"与 {trial_id} / {study_name} 登记记录配对",
                "notes": "通过 PubMed E-utilities 官方 API 核验 PMID、标题、期刊、日期和 DOI。",
            }
        )
        rows.append(row)
    return rows


def main() -> None:
    with REGISTRY.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        existing = list(reader)
    supplement_ids = {row["source_id"] for row in build_rows(fieldnames)}
    kept = [row for row in existing if row.get("source_id") not in supplement_ids]
    with REGISTRY.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept + build_rows(fieldnames))
    print(f"source_registry.csv updated: {len(kept) + len(supplement_ids)} rows")


if __name__ == "__main__":
    main()
