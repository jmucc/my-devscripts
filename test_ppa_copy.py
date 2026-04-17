from unittest.mock import MagicMock, patch, call
from ppa_copy import copy_packages


def make_pkg(name, series, version):
    pkg = MagicMock()
    pkg.source_package_name = name
    pkg.distro_series_link = f"https://api.launchpad.net/devel/ubuntu/{series}"
    pkg.source_package_version = version
    return pkg


def make_ppa(published):
    ppa = MagicMock()
    ppa.getPublishedSources.return_value = published
    return ppa


def test_copies_new_package():
    source = make_ppa([make_pkg("foo", "noble", "1.0-1")])
    dest = make_ppa([])

    copy_packages(source, dest, series=None, packages=None, dry_run=False)

    dest.copyPackage.assert_called_once_with(
        source_name="foo",
        version="1.0-1",
        from_archive=source,
        to_series="noble",
        to_pocket="Release",
        include_binaries=True,
    )


def test_copies_newer_version():
    source = make_ppa([make_pkg("foo", "noble", "2.0-1")])
    dest = make_ppa([make_pkg("foo", "noble", "1.0-1")])

    copy_packages(source, dest, series=None, packages=None, dry_run=False)

    dest.copyPackage.assert_called_once_with(
        source_name="foo",
        version="2.0-1",
        from_archive=source,
        to_series="noble",
        to_pocket="Release",
        include_binaries=True,
    )


def test_skips_same_version():
    source = make_ppa([make_pkg("foo", "noble", "1.0-1")])
    dest = make_ppa([make_pkg("foo", "noble", "1.0-1")])

    copy_packages(source, dest, series=None, packages=None, dry_run=False)

    dest.copyPackage.assert_not_called()


def test_skips_older_version():
    source = make_ppa([make_pkg("foo", "noble", "1.0-1")])
    dest = make_ppa([make_pkg("foo", "noble", "2.0-1")])

    copy_packages(source, dest, series=None, packages=None, dry_run=False)

    dest.copyPackage.assert_not_called()


def test_dry_run_does_not_copy():
    source = make_ppa([make_pkg("foo", "noble", "2.0-1")])
    dest = make_ppa([make_pkg("foo", "noble", "1.0-1")])

    copy_packages(source, dest, series=None, packages=None, dry_run=True)

    dest.copyPackage.assert_not_called()


def test_series_filter():
    source = make_ppa(
        [
            make_pkg("foo", "noble", "2.0-1"),
            make_pkg("foo", "jammy", "2.0-1"),
        ]
    )
    dest = make_ppa([])

    copy_packages(source, dest, series=["noble"], packages=None, dry_run=False)

    dest.copyPackage.assert_called_once()
    assert dest.copyPackage.call_args == call(
        source_name="foo",
        version="2.0-1",
        from_archive=source,
        to_series="noble",
        to_pocket="Release",
        include_binaries=True,
    )


def test_packages_filter():
    source = make_ppa(
        [
            make_pkg("foo", "noble", "2.0-1"),
            make_pkg("bar", "noble", "2.0-1"),
        ]
    )
    dest = make_ppa([])

    copy_packages(source, dest, series=None, packages=["bar"], dry_run=False)

    dest.copyPackage.assert_called_once()
    assert dest.copyPackage.call_args == call(
        source_name="bar",
        version="2.0-1",
        from_archive=source,
        to_series="noble",
        to_pocket="Release",
        include_binaries=True,
    )


def test_multiple_packages_copied():
    source = make_ppa(
        [
            make_pkg("foo", "noble", "1.0-1"),
            make_pkg("bar", "jammy", "3.0-1"),
        ]
    )
    dest = make_ppa([])

    copy_packages(source, dest, series=None, packages=None, dry_run=False)

    assert dest.copyPackage.call_count == 2
