"""Delete package/series combinations from a PPA that are absent from a reference PPA.

Any source package published for a given Ubuntu series in the PPA being trimmed
that does not have a matching package/series publication in the reference PPA is
deleted (via requestDeletion, which also removes its binaries).

Usage:
    python3 ppa_trim.py <user>/<ppa> <ref_user>/<ref_ppa> [--dry-run]

Example:
    python3 ppa_trim.py landscape/self-hosted-beta landscape/saas --dry-run
"""

import argparse
import os

from launchpadlib.launchpad import Launchpad


REMOVAL_COMMENT = "Trimmed: package/series not present in reference PPA"


def parse_ppa_ref(value):
    try:
        user, ppa = value.split("/", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "PPA reference must be in the form 'user/ppa'"
        ) from exc

    if not user or not ppa:
        raise argparse.ArgumentTypeError("PPA reference must be in the form 'user/ppa'")

    return user, ppa


def ppa_api_url(user, ppa):
    return f"https://api.launchpad.net/devel/~{user}/+archive/ubuntu/{ppa}"


def _split_version(version):
    """Split a Debian version into its (upstream, debian_revision) parts.

    The Debian revision is the component after the final hyphen; everything
    before it (including any epoch) identifies the upstream version.
    """
    if "-" in version:
        upstream, revision = version.rsplit("-", 1)
    else:
        upstream, revision = version, ""
    return upstream, revision


def version_difference(target_version, reference_version):
    """Classify how two versions differ.

    Returns None if equal, "revision" if only the Debian revision differs,
    and "version" if the upstream version (or epoch) differs.
    """
    if target_version == reference_version:
        return None

    target_upstream, _ = _split_version(target_version)
    reference_upstream, _ = _split_version(reference_version)

    if target_upstream == reference_upstream:
        return "revision"
    return "version"


def get_published_sources(ppa):
    return {
        (
            pkg.source_package_name,
            pkg.distro_series_link.split("/")[-1],
        ): pkg
        for pkg in ppa.getPublishedSources(status="Published")
    }


def trim_packages(target, reference, dry_run):
    target_pkgs = get_published_sources(target)
    reference_pkgs = get_published_sources(reference)

    for key, pub in target_pkgs.items():
        name, series = key

        if key in reference_pkgs:
            target_version = pub.source_package_version
            reference_version = reference_pkgs[key].source_package_version
            difference = version_difference(target_version, reference_version)
            if difference == "revision":
                print(
                    f"[warning] Debian revision mismatch: {name} for {series} "
                    f"(target {target_version}, reference {reference_version})"
                )
            elif difference == "version":
                print(
                    f"[warning] Version mismatch: {name} for {series} "
                    f"(target {target_version}, reference {reference_version})"
                )
            continue

        print(
            f"{'[dry-run] ' if dry_run else ''}Deleting: {name} for {series}"
        )
        if not dry_run:
            pub.requestDeletion(removal_comment=REMOVAL_COMMENT)


def main():
    parser = argparse.ArgumentParser(
        description="Delete package/series combinations from a PPA that are absent from a reference PPA"
    )
    parser.add_argument(
        "target",
        type=parse_ppa_ref,
        help="PPA to trim as user/ppa",
    )
    parser.add_argument(
        "reference",
        type=parse_ppa_ref,
        help="Reference PPA as user/ppa",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without actually deleting",
    )
    args = parser.parse_args()

    cache_dir = os.path.expanduser("~/.launchpadlib/cache/")
    lp = Launchpad.login_with("my-ppa-tool", "production", cache_dir, version="devel")
    print(f"Logged in as: {lp.me.display_name}")

    target_user, target_ppa = args.target
    reference_user, reference_ppa = args.reference

    target = lp.load(ppa_api_url(target_user, target_ppa))
    reference = lp.load(ppa_api_url(reference_user, reference_ppa))

    trim_packages(target, reference, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
