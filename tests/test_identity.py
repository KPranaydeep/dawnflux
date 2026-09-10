import pytest
from src.identity import owner_id

ISSUER = 'https://accounts.google.com'


def claims(**changes):
    return dict(dict(iss=ISSUER, sub='stable-id', email='owner@example.test', email_verified=True), **changes)


def test_identity_stable_not_email_based():
    a = owner_id(claims(), ['owner@example.test'], ISSUER)
    b = owner_id(claims(email='changed@example.test'), ['changed@example.test'], ISSUER)
    assert a == b and len(a) == 64
    assert a != owner_id(claims(sub='someone-else'), ['owner@example.test'], ISSUER)


@pytest.mark.parametrize('changes', [{'email_verified': False}, {'email_verified': 'true'}, {'sub': ''},
                                  {'email': 'other@example.test'}, {'iss': 'https://attacker.test'}])
def test_unauthorized_claims_rejected(changes):
    with pytest.raises(PermissionError):
        owner_id(claims(**changes), ['owner@example.test'], ISSUER)


def test_missing_allowlist_is_not_public_access():
    with pytest.raises(ValueError):
        owner_id(claims(), [], ISSUER)
