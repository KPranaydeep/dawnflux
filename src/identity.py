"""Authorize verified OIDC claims, never an email typed into a widget."""
import hashlib


def owner_id(claims, allowed_emails, issuer):
    if not isinstance(allowed_emails, (list, tuple)) or not allowed_emails:
        raise ValueError('An account allowlist is required.')
    if not issuer or claims.get('iss') != issuer:
        raise PermissionError('Unexpected sign-in provider.')
    email = claims.get('email', '')
    subject = claims.get('sub', '')
    if (claims.get('email_verified') is not True or not isinstance(email, str)
            or not isinstance(subject, str) or not subject.strip()
            or email.casefold() not in {str(x).casefold() for x in allowed_emails}):
        raise PermissionError('This account is not authorized for Dawnflux.')
    # Email may change; verified provider + stable subject is the ownership key.
    return hashlib.sha256((issuer + '\0' + subject).encode()).hexdigest()
