"""Copy existing binaries for published packages from one PPA to another.

Usage:
    python3 ppa-copy.py <source_user>/<source_ppa> <dest_user>/<dest_ppa> [--packages PACKAGES [PACKAGES ...]] [--series SERIES [SERIES ...]] [--dry-run]

Example:
    python3 ppa-copy.py landscape/self-hosted-beta landscape/saas --packages mypkg1 mypkg2 --series jammy noble --dry-run
"""

import argparse
import os
from launchpadlib.launchpad import Launchpad


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


def version_lt(ver1, ver2):
    """Return True if Debian version ver1 is less than ver2."""
    import apt_pkg

    apt_pkg.init_system()
    return apt_pkg.version_compare(ver1, ver2) < 0


def get_published_sources(ppa):
    return {
        (
            pkg.source_package_name,
            pkg.distro_series_link.split("/")[-1],
        ): pkg.source_package_version
        for pkg in ppa.getPublishedSources(status="Published")
    }


def copy_packages(source, dest, series, packages, dry_run):
    s_pkgs = get_published_sources(source)
    d_pkgs = get_published_sources(dest)

    for key, value in s_pkgs.items():
        name, s = key
        ver = value

        if series and s not in series:
            continue

        if packages and name not in packages:
            continue

        if key not in d_pkgs or version_lt(d_pkgs[key], ver):
            print(
                f"{'[dry-run] ' if dry_run else ''}Copying: {name} for {s} ({d_pkgs.get(key, 'None')} -> {ver})"
            )
            if not dry_run:
                dest.copyPackage(
                    source_name=name,
                    version=ver,
                    from_archive=source,
                    to_series=s,
                    to_pocket="Release",
                    include_binaries=True,
                )


def main():
    parser = argparse.ArgumentParser(
        description="Copy existing binaries for published packages from source PPA to destination PPA"
    )
    parser.add_argument(
        "source",
        type=parse_ppa_ref,
        help="Source PPA as user/ppa",
    )
    parser.add_argument(
        "dest",
        type=parse_ppa_ref,
        help="Destination PPA as user/ppa",
    )
    parser.add_argument(
        "--packages",
        nargs="+",
        metavar="PACKAGES",
        help="Limit to one or more packages (e.g. --packages mypkg1 mypkg2)",
    )
    parser.add_argument(
        "--series",
        nargs="+",
        metavar="SERIES",
        help="Limit to one or more Ubuntu series (e.g. --series focal noble)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be copied without actually copying",
    )
    args = parser.parse_args()

    cache_dir = os.path.expanduser("~/.launchpadlib/cache/")
    lp = Launchpad.login_with("my-ppa-tool", "production", cache_dir, version="devel")
    print(f"Logged in as: {lp.me.display_name}")

    source_user, source_ppa = args.source
    dest_user, dest_ppa = args.dest

    source = lp.load(ppa_api_url(source_user, source_ppa))
    dest = lp.load(ppa_api_url(dest_user, dest_ppa))

    copy_packages(
        source, dest, series=args.series, packages=args.packages, dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
