"""Unit tests for Email value object (REQ-017, REQ-021)."""

import pytest

from leadhunter.domain.exceptions import InvalidEmailFormatError
from leadhunter.domain.value_objects.email import Email


class TestEmailNormalization:
    """Tests for email normalization (REQ-017)."""

    def test_valid_email_lowercases(self) -> None:
        """REQ-017: Email is converted to lowercase."""
        email = Email("User@Example.COM")
        assert email.value == "user@example.com"

    def test_valid_email_strips_whitespace(self) -> None:
        """REQ-017: Leading/trailing whitespace is removed."""
        email = Email("  user@example.com  ")
        assert email.value == "user@example.com"

    def test_valid_email_standard(self) -> None:
        """Standard email address is accepted."""
        email = Email("sales@company.co.uk")
        assert email.value == "sales@company.co.uk"

    def test_valid_email_with_plus(self) -> None:
        """Email with + in local-part is accepted."""
        email = Email("user+tag@example.com")
        assert email.value == "user+tag@example.com"

    def test_valid_email_with_dots(self) -> None:
        """Email with dots in local-part is accepted."""
        email = Email("first.last@domain.org")
        assert email.value == "first.last@domain.org"


class TestEmailValidation:
    """Tests for email validation failure (REQ-017, REQ-021)."""

    def test_invalid_email_no_at_sign_raises(self) -> None:
        """REQ-021: Invalid email raises InvalidEmailFormatError at init time."""
        with pytest.raises(InvalidEmailFormatError) as exc_info:
            Email("notanemail")
        assert exc_info.value.error_code == "INVALID_EMAIL_FORMAT"

    def test_invalid_email_no_domain_raises(self) -> None:
        """Missing domain part raises InvalidEmailFormatError."""
        with pytest.raises(InvalidEmailFormatError):
            Email("user@")

    def test_invalid_email_no_tld_raises(self) -> None:
        """Domain without TLD raises InvalidEmailFormatError."""
        with pytest.raises(InvalidEmailFormatError):
            Email("user@nodomain")

    def test_empty_email_raises(self) -> None:
        """Empty string raises InvalidEmailFormatError."""
        with pytest.raises(InvalidEmailFormatError):
            Email("")

    def test_whitespace_only_email_raises(self) -> None:
        """Whitespace-only string raises InvalidEmailFormatError."""
        with pytest.raises(InvalidEmailFormatError):
            Email("   ")

    def test_email_with_spaces_in_middle_raises(self) -> None:
        """Email with spaces in middle raises InvalidEmailFormatError."""
        with pytest.raises(InvalidEmailFormatError):
            Email("user @example.com")


class TestEmailEquality:
    """Tests for Email equality and hashing (REQ-021 immutability)."""

    def test_equal_emails_are_equal(self) -> None:
        """Two emails with same value are equal."""
        assert Email("user@example.com") == Email("user@example.com")

    def test_case_different_emails_are_equal_after_normalization(self) -> None:
        """Emails normalised to same lowercase are equal."""
        assert Email("USER@EXAMPLE.COM") == Email("user@example.com")

    def test_different_emails_are_not_equal(self) -> None:
        """Different emails are not equal."""
        assert Email("a@example.com") != Email("b@example.com")

    def test_email_is_hashable(self) -> None:
        """Email can be used in sets and as dict keys."""
        emails = {Email("user@example.com"), Email("USER@EXAMPLE.COM")}
        assert len(emails) == 1  # Both normalise to same

    def test_email_str_repr(self) -> None:
        """str() returns the normalised value."""
        assert str(Email("USER@EXAMPLE.COM")) == "user@example.com"
