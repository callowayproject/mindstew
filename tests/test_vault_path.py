"""vault_path: the one "is this relative path safely inside the vault" check."""

import pytest

from mindstew.vault import vault_path


def test_resolves_a_relative_path_inside_the_vault(tmp_path):
    """Behaviour of vault_path."""
    (tmp_path / "sources").mkdir()
    assert vault_path(tmp_path, "sources/a.md") == (tmp_path / "sources" / "a.md").resolve()


def test_missing_file_still_resolves(tmp_path):
    """Behaviour of vault_path."""
    assert vault_path(tmp_path, "sources/nope.md") == (tmp_path / "sources" / "nope.md").resolve()


@pytest.mark.parametrize(
    "rel",
    ["/etc/passwd", "\\evil", "../x", "a/../../x", "a\\..\\..\\x", "..", "", "a\0b", None, 3, b"a", ["a"], {"a": 1}],
)
def test_rejects_unsafe_or_malformed(tmp_path, rel):
    """Behaviour of vault_path."""
    assert vault_path(tmp_path, rel) is None


def test_rejects_symlink_pointing_out(tmp_path):
    """Behaviour of vault_path."""
    outside = tmp_path / "outside"
    outside.mkdir()
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "link").symlink_to(outside)
    assert vault_path(vault, "link/secret.md") is None
