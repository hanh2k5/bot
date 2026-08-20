"""Domain services package."""

from leadhunter.domain.services.dedup_service import (
    DeduplicationConfig,
    compute_company_phone_dedup_key,
    compute_email_dedup_key,
)
from leadhunter.domain.services.normalization_service import (
    normalize_address,
    normalize_company_name,
    normalize_contact_name,
    normalize_email,
    normalize_phone,
    normalize_website,
)
from leadhunter.domain.services.scoring_service import (
    ScoringRule,
    ScoringRules,
    compute_score,
)
from leadhunter.domain.services.status_service import validate_transition

__all__ = [
    "DeduplicationConfig",
    "ScoringRule",
    "ScoringRules",
    "compute_company_phone_dedup_key",
    "compute_email_dedup_key",
    "compute_score",
    "normalize_address",
    "normalize_company_name",
    "normalize_contact_name",
    "normalize_email",
    "normalize_phone",
    "normalize_website",
    "validate_transition",
]
