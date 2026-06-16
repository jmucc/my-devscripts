from unittest.mock import MagicMock
from ppa_trim import trim_packages, version_difference, REMOVAL_COMMENT


def make_pkg(name, series, version="1.0-1"):
    pkg = MagicMock()
    pkg.source_package_name = name
    pkg.distro_series_link = f"https://api.launchpad.net/devel/ubuntu/{series}"
    pkg.source_package_version = version
    return pkg


def make_ppa(published):
    ppa = MagicMock()
    ppa.getPublishedSources.return_value = published
    return ppa


def test_deletes_package_absent_from_reference():
    pkg = make_pkg("foo", "noble")
    target = make_ppa([pkg])
    reference = make_ppa([])

    trim_packages(target, reference, dry_run=False)

    pkg.requestDeletion.assert_called_once_with(removal_comment=REMOVAL_COMMENT)


def test_keeps_package_present_in_reference():
    pkg = make_pkg("foo", "noble")
    target = make_ppa([pkg])
    reference = make_ppa([make_pkg("foo", "noble")])

    trim_packages(target, reference, dry_run=False)

    pkg.requestDeletion.assert_not_called()


def test_series_combination_matters():
    # Same package name, but the series differs from the reference.
    pkg = make_pkg("foo", "jammy")
    target = make_ppa([pkg])
    reference = make_ppa([make_pkg("foo", "noble")])

    trim_packages(target, reference, dry_run=False)

    pkg.requestDeletion.assert_called_once_with(removal_comment=REMOVAL_COMMENT)


def test_keeps_matching_series_deletes_other():
    keep = make_pkg("foo", "noble")
    drop = make_pkg("foo", "jammy")
    target = make_ppa([keep, drop])
    reference = make_ppa([make_pkg("foo", "noble")])

    trim_packages(target, reference, dry_run=False)

    keep.requestDeletion.assert_not_called()
    drop.requestDeletion.assert_called_once_with(removal_comment=REMOVAL_COMMENT)


def test_dry_run_does_not_delete():
    pkg = make_pkg("foo", "noble")
    target = make_ppa([pkg])
    reference = make_ppa([])

    trim_packages(target, reference, dry_run=True)

    pkg.requestDeletion.assert_not_called()


def test_deletes_multiple_packages():
    foo = make_pkg("foo", "noble")
    bar = make_pkg("bar", "jammy")
    target = make_ppa([foo, bar])
    reference = make_ppa([])

    trim_packages(target, reference, dry_run=False)

    foo.requestDeletion.assert_called_once_with(removal_comment=REMOVAL_COMMENT)
    bar.requestDeletion.assert_called_once_with(removal_comment=REMOVAL_COMMENT)


def test_version_difference_is_not_trimmed():
    # Trimming is by package/series only, not version, so a version mismatch
    # for the same package/series is kept.
    pkg = make_pkg("foo", "noble", version="2.0-1")
    target = make_ppa([pkg])
    reference = make_ppa([make_pkg("foo", "noble", version="1.0-1")])

    trim_packages(target, reference, dry_run=False)

    pkg.requestDeletion.assert_not_called()


# --- version_difference helper ---------------------------------------------


def test_version_difference_equal():
    assert version_difference("1.0-1", "1.0-1") is None


def test_version_difference_revision_only():
    assert version_difference("1.0-1", "1.0-2") == "revision"


def test_version_difference_entirely_different_upstream():
    assert version_difference("1.0-1", "2.0-1") == "version"


def test_version_difference_revision_with_epoch():
    assert version_difference("1:1.0-1", "1:1.0-2") == "revision"


def test_version_difference_different_epoch_is_version():
    assert version_difference("2:1.0-1", "1:1.0-1") == "version"


def test_version_difference_missing_revision_counts_as_revision():
    assert version_difference("1.0", "1.0-1") == "revision"


def test_version_difference_native_packages_no_revision():
    assert version_difference("1.0", "1.0") is None
    assert version_difference("1.0", "2.0") == "version"


def test_version_difference_upstream_with_hyphen():
    # Upstream version itself contains a hyphen; only the trailing component
    # is the Debian revision.
    assert version_difference("1.0-beta-1", "1.0-beta-2") == "revision"
    assert version_difference("1.0-beta-1", "1.1-beta-1") == "version"


# --- version mismatch warnings ---------------------------------------------


def test_warns_on_revision_mismatch(capsys):
    pkg = make_pkg("foo", "noble", version="1.0-1")
    target = make_ppa([pkg])
    reference = make_ppa([make_pkg("foo", "noble", version="1.0-2")])

    trim_packages(target, reference, dry_run=False)

    out = capsys.readouterr().out
    pkg.requestDeletion.assert_not_called()
    assert "revision" in out.lower()
    assert "foo" in out
    assert "noble" in out
    assert "1.0-1" in out
    assert "1.0-2" in out


def test_warns_on_version_mismatch(capsys):
    pkg = make_pkg("foo", "noble", version="1.0-1")
    target = make_ppa([pkg])
    reference = make_ppa([make_pkg("foo", "noble", version="2.0-1")])

    trim_packages(target, reference, dry_run=False)

    out = capsys.readouterr().out
    pkg.requestDeletion.assert_not_called()
    assert "version mismatch" in out.lower()
    assert "1.0-1" in out
    assert "2.0-1" in out


def test_no_warning_when_versions_match(capsys):
    pkg = make_pkg("foo", "noble", version="1.0-1")
    target = make_ppa([pkg])
    reference = make_ppa([make_pkg("foo", "noble", version="1.0-1")])

    trim_packages(target, reference, dry_run=False)

    out = capsys.readouterr().out
    assert "mismatch" not in out.lower()


def test_no_warning_for_deleted_packages(capsys):
    # A package absent from the reference is deleted, not version-checked.
    pkg = make_pkg("foo", "noble", version="1.0-1")
    target = make_ppa([pkg])
    reference = make_ppa([])

    trim_packages(target, reference, dry_run=False)

    out = capsys.readouterr().out
    assert "mismatch" not in out.lower()


def test_warnings_emitted_during_dry_run(capsys):
    pkg = make_pkg("foo", "noble", version="1.0-1")
    target = make_ppa([pkg])
    reference = make_ppa([make_pkg("foo", "noble", version="1.0-2")])

    trim_packages(target, reference, dry_run=True)

    out = capsys.readouterr().out
    assert "revision" in out.lower()
