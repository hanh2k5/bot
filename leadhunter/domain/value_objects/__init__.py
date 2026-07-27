"""Value objects package."""

from leadhunter.domain.value_objects.company_name import CompanyName
from leadhunter.domain.value_objects.email import Email
from leadhunter.domain.value_objects.phone_number import PhoneNumber
from leadhunter.domain.value_objects.website import Website

__all__ = ["CompanyName", "Email", "PhoneNumber", "Website"]
