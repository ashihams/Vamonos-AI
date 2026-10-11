"""Pick the cheap or strong model tier for one company."""

from costwise.domain.company import CompanyRecord
from costwise.domain.config import RoutingPolicy
from costwise.domain.icp import IcpRule, is_near_threshold, missing_field_count
from costwise.domain.task import ModelTier


class RoutingService:
    """Escalate hard-looking companies to the strong tier."""

    def choose(self, record: CompanyRecord, policy: RoutingPolicy, rule: IcpRule) -> ModelTier:
        """Return STRONG for missing-field or near-threshold cases the policy flags."""
        threshold = policy.strong_if_missing_fields_gte
        if threshold > 0 and missing_field_count(record, rule) >= threshold:
            return ModelTier.STRONG
        if policy.strong_if_near_threshold and is_near_threshold(record, rule):
            return ModelTier.STRONG
        return policy.default_tier
