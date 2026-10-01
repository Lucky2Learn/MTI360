"""Audit vocabulary: categories (T01-02; ADR-0013).

The category is the broad classification of an audit event. The set is
closed; the database enforces it with a check constraint.
"""

from enum import StrEnum


class AuditCategory(StrEnum):
    """Approved audit categories (ADR-0013 §2)."""

    SECURITY = "security"
    """Authentication, authorization and abuse signals. Written through the
    security-event buffer, after the request transaction (ADR-0013 §5)."""
    ADMIN = "admin"
    """Administrative changes: tenants, users, roles, configuration."""
    DATA_ACCESS = "data_access"
    """Reads of sensitive data that must be traceable (support access, exports)."""
    DOMAIN = "domain"
    """Business changes recorded with the mutation (finance, compliance, …)."""
