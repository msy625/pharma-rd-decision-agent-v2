"""Explicit relationship projection for the curated normalized website data.

This module never joins records by names or titles.  A projected chain exists
only when the normalized tables explicitly identify a study, source, asset, or
regulatory event relationship.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from deepinsight.core.source_registry_service import norm
from deepinsight.core.template_data_repository import TemplateDataRepository


STUDY_SOURCE_RELATIONS = {"source_describes_study", "source_supports"}


class NormalizedEvidenceChainProjection:
    """Project studies, regulatory events, and organization coverage from CSV relations."""

    def __init__(self, repository: TemplateDataRepository | None = None) -> None:
        self.repository = repository or TemplateDataRepository()

    def study_chains(self) -> list[dict[str, Any]]:
        studies = self.repository.load_table("studies")
        identifiers = self.repository.load_table("study_identifiers")
        organizations = {row["organization_id"]: row for row in self.repository.load_table("organizations")}
        source_rows = {row["template_source_id"]: row for row in self.repository.source_rows(domain_id=None)}
        source_ids_by_study: dict[str, set[str]] = defaultdict(set)
        for relation in self.repository.load_table("relations"):
            if relation.get("relation_status") != "confirmed":
                continue
            if relation.get("relation_type") not in STUDY_SOURCE_RELATIONS:
                continue
            if relation.get("object_id", "").startswith("STUDY_"):
                source_ids_by_study[relation["object_id"]].add(relation.get("source_id", ""))

        identifiers_by_study: dict[str, list[str]] = defaultdict(list)
        for identifier in identifiers:
            if identifier.get("identifier_value"):
                identifiers_by_study[identifier.get("study_id", "")].append(identifier["identifier_value"])

        chains = []
        for study in studies:
            study_id = study["study_id"]
            source_rows_for_study = [source_rows[source_id] for source_id in sorted(source_ids_by_study.get(study_id, set())) if source_id in source_rows]
            if len(source_rows_for_study) >= 2:
                status, gaps = "formed", []
            elif len(source_rows_for_study) == 1:
                status, gaps = "single_source", ["当前仅有一条已确认来源，尚未形成多来源证据链。"]
            else:
                status, gaps = "relationship_insufficient", ["当前未收录指向该研究的已确认来源关系，不能自动补关联。"]
            sponsor = organizations.get(study.get("sponsor_org_id", ""), {})
            chains.append({
                "chain_id": f"projected:study:{study_id}",
                "chain_type": "trial",
                "chain_origin": "template_projection",
                "projection_status": status,
                "relation_level": "study",
                "study_id": study_id,
                "chain_name": study.get("study_name") or study_id,
                "company_name": sponsor.get("canonical_name", ""),
                "company_display_name": sponsor.get("display_name", ""),
                "drug_names": [],
                "trial_ids": sorted(set(identifiers_by_study.get(study_id, []))),
                "study_names": [study.get("study_name", "")] if study.get("study_name") else [],
                "study_status": study.get("study_status", ""),
                "evidence_rows": source_rows_for_study,
                "evidence_gaps": gaps,
                "risk_notes": [],
            })
        return chains

    def regulatory_chains(self) -> list[dict[str, Any]]:
        events = {row["regulatory_event_id"]: row for row in self.repository.load_table("regulatory_events")}
        assets = {row["asset_id"]: row for row in self.repository.load_table("assets")}
        organizations = {row["organization_id"]: row for row in self.repository.load_table("organizations")}
        source_rows = {row["template_source_id"]: row for row in self.repository.source_rows(domain_id=None)}
        event_ids_by_asset: dict[str, set[str]] = defaultdict(set)
        source_ids_by_asset: dict[str, set[str]] = defaultdict(set)
        for relation in self.repository.load_table("relations"):
            if relation.get("relation_status") != "confirmed" or relation.get("relation_type") != "has_regulatory_event":
                continue
            asset_id, event_id = relation.get("subject_id", ""), relation.get("object_id", "")
            if asset_id in assets and event_id in events:
                event_ids_by_asset[asset_id].add(event_id)
                if relation.get("source_id"):
                    source_ids_by_asset[asset_id].add(relation["source_id"])

        chains = []
        for asset_id, event_ids in sorted(event_ids_by_asset.items()):
            asset = assets[asset_id]
            event_rows = [events[event_id] for event_id in sorted(event_ids)]
            source_ids = set(source_ids_by_asset[asset_id]) | {event.get("source_id", "") for event in event_rows}
            evidence_rows = [source_rows[source_id] for source_id in sorted(source_ids) if source_id in source_rows]
            holder_ids = {event.get("holder_org_id", "") for event in event_rows}
            holder = organizations.get(next(iter(holder_ids), ""), {}) if len(holder_ids) == 1 else {}
            names = [asset.get(key, "") for key in ("canonical_name", "generic_name", "development_code", "brand_name")]
            chains.append({
                "chain_id": f"projected:regulatory:{asset_id}",
                "chain_type": "regulatory",
                "chain_origin": "template_projection",
                "projection_status": "formed" if evidence_rows else "relationship_insufficient",
                "relation_level": "asset_regulatory_event",
                "asset_id": asset_id,
                "chain_name": f"{asset.get('display_name') or asset.get('canonical_name') or asset_id} 监管事件链",
                "company_name": holder.get("canonical_name", ""),
                "company_display_name": holder.get("display_name", ""),
                "drug_names": [name for name in names if name],
                "trial_ids": [],
                "study_names": [],
                "study_status": "",
                "evidence_rows": evidence_rows,
                "regulatory_events": event_rows,
                "evidence_gaps": [] if evidence_rows else ["监管事件已确认，但当前没有可展示的已确认来源关系。"],
                "risk_notes": [],
            })
        return chains

    def organization_coverage(self, identifier: str) -> dict[str, Any]:
        key = norm(identifier)
        organization = next((row for row in self.repository.load_table("organizations") if key in {norm(row.get("organization_id")), norm(row.get("canonical_name")), norm(row.get("display_name"))}), None)
        if not organization:
            return {}
        organization_id = organization["organization_id"]
        studies = [row for row in self.repository.load_table("studies") if row.get("sponsor_org_id") == organization_id]
        source_ids = {
            row.get("source_id", "") for row in self.repository.load_table("relations")
            if row.get("relation_status") == "confirmed" and row.get("relation_type") in {"source_about", "source_about_org"} and row.get("object_id") == organization_id
        }
        sources = [row for row in self.repository.source_rows(domain_id=None) if row.get("template_source_id") in source_ids]
        return {
            "organization": organization,
            "coverage": {
                "explicit_source_count": len(sources),
                "sponsored_study_count": len(studies),
                "study_ids": [row["study_id"] for row in studies],
                "source_ids": [row["source_id"] for row in sources],
            },
        }
