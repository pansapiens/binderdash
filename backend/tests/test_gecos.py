"""Tests for GECOS-derived PAM emails.

Only the 5th GECOS field ("other") is read, because it is the one field chfn
cannot write -- see GECOS_EMAIL_FIELD in backend/auth_providers/pam.py. Reading
any earlier field would let a shell user claim a colleague's address via
`chfn -r` and be merged into their account, inheriting its API keys and admin.
"""

import pytest

from backend.auth_providers.pam import gecos_email


# --- the 5th field is read --------------------------------------------------


@pytest.mark.parametrize(
    "gecos,expected",
    [
        # The shape rotibom uses after the fix: name, three empties, email.
        ("localuser,,,,alice@example.org", "alice@example.org"),
        ("rbamert,,,,bob@example.org", "bob@example.org"),
        ("vxue0002,,,,student1@example.org", "student1@example.org"),
        # Hyphenated local part.
        ("mhad0012,,,,carol@example.org", "carol@example.org"),
        # Hyphenated, multi-label domain.
        ("Jane Doe,,,,jane@some-domain.co.uk", "jane@some-domain.co.uk"),
        # A trailing note alongside the address is tolerated.
        ("u,,,,someone@example.org (primary)", "someone@example.org"),
        # Other fields populated is fine, as long as field 5 holds the address.
        ("Full Name,Room 1,555,556,person@example.org", "person@example.org"),
    ],
)
def test_reads_address_from_fifth_field(gecos, expected):
    assert gecos_email(gecos) == expected


# --- every other field is ignored -------------------------------------------


@pytest.mark.parametrize(
    "gecos",
    [
        # The pre-fix rotibom shape: address in field 2 (room). Must be ignored,
        # because a user can set that themselves with `chfn -r`.
        "localuser,alice@example.org created by localuser,,",
        "vxue0002,student1@example.org created by localuser,,",
        # Field 1 (full name).
        "alice@example.org,,,",
        # Field 4 (home phone) -- user-writable under CHFN_RESTRICT rwh.
        "localuser,,,alice@example.org",
        # Someone filling every writable field but not the 5th.
        "victim@example.org,victim@example.org,victim@example.org,victim@example.org",
    ],
)
def test_ignores_addresses_outside_the_fifth_field(gecos):
    assert gecos_email(gecos) is None


@pytest.mark.parametrize(
    "gecos",
    [
        "",
        "Ubuntu",
        "localuser,,,,",
        "localuser,,,,not-an-address",
        "localuser,,,,@nolocalpart.org",
        # Fewer than five fields at all.
        "a,b,c,d",
    ],
)
def test_no_address_yields_none(gecos):
    assert gecos_email(gecos) is None


def test_a_sixth_field_does_not_shift_the_read():
    # Extra trailing fields must not change which field is authoritative.
    assert gecos_email("u,,,,real@example.org,other@example.org") == "real@example.org"


# --- the feature is opt-in --------------------------------------------------


def test_lookup_disabled_unless_flag_set(monkeypatch):
    import backend.auth_providers.pam as pam_mod

    class FakePwd:
        @staticmethod
        def getpwnam(_name):
            class Entry:
                pw_gecos = "localuser,,,,alice@example.org"

            return Entry()

    monkeypatch.setattr(pam_mod, "pwd", FakePwd)

    off = pam_mod.settings.model_copy(update={"pam_gecos_email": False})
    monkeypatch.setattr(pam_mod, "settings", off)
    assert pam_mod._lookup_gecos_email("localuser") is None

    on = pam_mod.settings.model_copy(update={"pam_gecos_email": True})
    monkeypatch.setattr(pam_mod, "settings", on)
    assert pam_mod._lookup_gecos_email("localuser") == "alice@example.org"
