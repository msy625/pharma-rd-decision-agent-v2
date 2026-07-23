"""Evidence chain service for manually confirmed NSCLC source relationships.

This module only reads local JSON/CSV-backed services. It intentionally avoids
model, vector-store, network, or web framework dependencies.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from deepinsight.core.source_registry_service import (
    PROJECT_ROOT,
    SourceRegistryFileNotFound,
    SourceRegistryService,
    SourceRegistryStructureError,
    contains,
    norm,
)


DEFAULT_CHAIN_CONFIG_PATH = PROJECT_ROOT / "config" / "evidence_chains.json"

REGULATORY_ROLES = {"regulatory_authorisation", "regulatory_opinion"}
INDEPENDENT_ROLES = {"company_document", "independent_evidence"}


class EvidenceChainService:
    """Build evidence-chain responses from config plus source registry rows."""

    def __init__(
        self,
        *,
        chain_config_path: str | Path | None = None,
        source_registry_service: SourceRegistryService | None = None,
    ) -> None:
        self.chain_config_path = Path(chain_config_path) if chain_config_path else DEFAULT_CHAIN_CONFIG_PATH
        self.source_registry_service = source_registry_service or SourceRegistryService()
        self._chain_config: dict[str, object] | None = None

    def load_chain_config(self) -> dict[str, object]:
        if self._chain_config is None:
            self._chain_config = load_chain_config(self.chain_config_path)
        return dict(self._chain_config)

    def list_chains(self, company: str | None = None, chain_type: str | None = None) -> list[dict[str, object]]:
        chains = []
        company_terms = self.source_registry_service.expand_company_terms(company) if company else []
        for chain_config in self._configured_chains():
            if company_terms and not any(
                contains(chain_config.get("company_name"), term) for term in company_terms
            ):
                continue
            if chain_type and chain_config.get("chain_type") != chain_type:
                continue
            chains.append(self._build_chain(chain_config))
        return chains

    def get_chain(self, chain_id: str) -> dict[str, object]:
        if not chain_id:
            return {}
        for chain_config in self._configured_chains():
            if chain_config.get("chain_id") == chain_id:
                return self._build_chain(chain_config)
        return {}

    def get_trial_chain(self, trial_id: str) -> dict[str, object]:
        if not trial_id:
            return {}
        trial_id_key = norm(trial_id)
        for chain_config in self._configured_chains():
            if chain_config.get("chain_type") != "trial":
                continue
            trial_ids = [norm(item) for item in chain_config.get("trial_ids", [])]
            if trial_id_key in trial_ids:
                return self._build_chain(chain_config)
        return {}

    def get_drug_regulatory_chain(self, drug_name: str) -> dict[str, object]:
        if not drug_name:
            return {}
        aliases = self.source_registry_service.load_aliases()
        terms = [norm(item) for item in self.source_registry_service.expand_drug_terms(drug_name, aliases)]
        for chain_config in self._configured_chains():
            if chain_config.get("chain_type") != "regulatory":
                continue
            chain_drugs = [norm(item) for item in chain_config.get("drug_names", [])]
            if any(term in chain_drugs for term in terms):
                return self._build_chain(chain_config)
        return {}

    def get_unresolved_links(self) -> list[dict[str, object]]:
        source_map = self._source_map()
        unresolved = []
        for item in self.load_chain_config().get("unresolved_links", []):
            if not isinstance(item, dict):
                continue
            row = source_map.get(str(item.get("source_id", "")))
            enriched = dict(item)
            enriched["source"] = self._normalize_with_role(row, "independent_evidence") if row else {}
            unresolved.append(enriched)
        return unresolved

    def summary(self) -> dict[str, object]:
        chains = self.list_chains()
        trial_chains = [chain for chain in chains if chain["chain_type"] == "trial"]
        regulatory_chains = [chain for chain in chains if chain["chain_type"] == "regulatory"]
        nct_registered_trial_ids = {
            trial_id for chain in trial_chains for trial_id in chain.get("trial_ids", []) if str(trial_id).startswith("NCT")
        }
        company_counts = Counter(str(chain.get("company_name", "")) for chain in chains)
        return {
            "total_chains": len(chains),
            "trial_chains": len(trial_chains),
            "regulatory_chains": len(regulatory_chains),
            "clinical_trial_count": len(trial_chains),
            "nct_registered_trial_count": len(nct_registered_trial_ids),
            "nct_registered_trial_ids": sorted(nct_registered_trial_ids),
            "company_counts": dict(company_counts),
            "unresolved_links": len(self.get_unresolved_links()),
        }

    def _configured_chains(self) -> list[dict[str, object]]:
        chains = self.load_chain_config().get("chains", [])
        return [chain for chain in chains if isinstance(chain, dict)]

    def _source_map(self) -> dict[str, dict[str, str]]:
        return {row.get("source_id", ""): row for row in self.source_registry_service.load_rows()}

    def _build_chain(self, chain_config: dict[str, object]) -> dict[str, object]:
        source_map = self._source_map()
        evidence_items = []
        for source_ref in chain_config.get("source_ids", []):
            if not isinstance(source_ref, dict):
                continue
            source_id = str(source_ref.get("source_id", ""))
            role = str(source_ref.get("role", "independent_evidence"))
            row = source_map.get(source_id)
            if row:
                evidence_items.append(self._normalize_with_role(row, role))

        related_regulatory_items = []
        for source_id in chain_config.get("related_regulatory_source_ids", []):
            row = source_map.get(str(source_id))
            if row:
                related_regulatory_items.append(self._normalize_with_role(row, "regulatory_opinion"))

        return {
            "chain_id": chain_config.get("chain_id", ""),
            "chain_name": chain_config.get("chain_name", ""),
            "chain_type": chain_config.get("chain_type", ""),
            "relation_level": chain_config.get("relation_level", ""),
            "company_name": chain_config.get("company_name", ""),
            "drug_names": list(chain_config.get("drug_names", [])),
            "trial_ids": list(chain_config.get("trial_ids", [])),
            "related_trial_ids": list(chain_config.get("related_trial_ids", [])),
            "study_names": list(chain_config.get("study_names", [])),
            "study_status": self._chain_study_status(evidence_items),
            "evidence_items": evidence_items,
            "latest_items": [item for item in evidence_items if item.get("version_status") == "latest"],
            "historical_items": [item for item in evidence_items if item.get("version_status") == "historical"],
            "independent_items": [item for item in evidence_items if item.get("version_status") == "independent"],
            "regulatory_items": [item for item in evidence_items if item.get("role") in REGULATORY_ROLES],
            "related_regulatory_items": related_regulatory_items,
            "evidence_gaps": list(chain_config.get("evidence_gaps", [])),
            "risk_notes": list(chain_config.get("risk_notes", [])),
            "source_count": len(evidence_items),
        }

    def _normalize_with_role(self, row: dict[str, str], role: str) -> dict[str, str]:
        normalized = self.source_registry_service.normalize_row(row)
        normalized.update(
            {
                "role": role,
                "registry_id": row.get("registry_id", ""),
                "publication_date": row.get("publication_date", ""),
                "source_last_updated": row.get("source_last_updated", ""),
                "analysis_stage": row.get("analysis_stage", ""),
                "evidence_version": row.get("evidence_version", ""),
                "supersedes_source_id": row.get("supersedes_source_id", ""),
                "version_status": version_status(row.get("is_latest_evidence", "")),
            }
        )
        return normalized

    @staticmethod
    def _chain_study_status(items: Iterable[dict[str, str]]) -> str:
        for item in items:
            if item.get("role") == "trial_registry" and item.get("study_status"):
                return item["study_status"]
        for item in items:
            if item.get("study_status"):
                return item["study_status"]
        return ""


def load_chain_config(path: str | Path | None = None) -> dict[str, object]:
    config_path = Path(path) if path else DEFAULT_CHAIN_CONFIG_PATH
    if not config_path.exists():
        raise SourceRegistryFileNotFound(f"Required evidence chain config not found: {config_path}")
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SourceRegistryStructureError(f"Evidence chain config JSON is invalid: {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SourceRegistryStructureError(f"Evidence chain config root must be an object: {config_path}")
    if not isinstance(data.get("chains"), list):
        raise SourceRegistryStructureError(f"Evidence chain config must contain a chains list: {config_path}")
    return data


def list_chains(company: str | None = None, chain_type: str | None = None) -> list[dict[str, object]]:
    return EvidenceChainService().list_chains(company=company, chain_type=chain_type)


def get_chain(chain_id: str) -> dict[str, object]:
    return EvidenceChainService().get_chain(chain_id)


def get_trial_chain(trial_id: str) -> dict[str, object]:
    return EvidenceChainService().get_trial_chain(trial_id)


def get_drug_regulatory_chain(drug_name: str) -> dict[str, object]:
    return EvidenceChainService().get_drug_regulatory_chain(drug_name)


def get_unresolved_links() -> list[dict[str, object]]:
    return EvidenceChainService().get_unresolved_links()


def summary() -> dict[str, object]:
    return EvidenceChainService().summary()


def version_status(value: object) -> str:
    value_key = norm(value)
    if value_key == "true":
        return "latest"
    if value_key == "false":
        return "historical"
    return "independent"
