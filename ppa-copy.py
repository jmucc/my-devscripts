"""Copy published source packages from one PPA to another for a single Ubuntu series.

Usage:
    python3 ppa-copy.py <source_user>/<source_ppa> <dest_user>/<dest_ppa> <series>

Example:
    python3 ppa-copy.py landscape/self-hosted-beta landscape/saas noble
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
        raise argparse.ArgumentTypeError(
            "PPA reference must be in the form 'user/ppa'"
        )

    return user, ppa


def ppa_api_url(user, ppa):
    return f"https://api.launchpad.net/devel/~{user}/+archive/ubuntu/{ppa}"


def get_published_sources(ppa, series):
    series_url = f"https://api.launchpad.net/1.0/ubuntu/{series}"
    return {
        p.source_package_name: p.source_package_version
        for p in ppa.getPublishedSources(distro_series=series_url, status="Published")
    }


def main():
    parser = argparse.ArgumentParser(
        description="Copy packages from source PPA to destination PPA for one Ubuntu series"
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
        "series",
        help="Ubuntu series name (for example: focal, jammy, noble)",
    )
    parser.add_argument(
        "--package",
        metavar="SUBSTRING",
        help="Limit to packages whose name contains this substring",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be copied without actually copying",
    )
    args = parser.parse_args()

    cache_dir = os.path.expanduser("~/.launchpadlib/cache/")
    lp = Launchpad.login_with('my-ppa-tool', 'production', cache_dir, version='devel')
    print(f"Logged in as: {lp.me.display_name}")

    source_user, source_ppa = args.source
    dest_user, dest_ppa = args.dest
    series = args.series

    source = lp.load(ppa_api_url(source_user, source_ppa))
    dest = lp.load(ppa_api_url(dest_user, dest_ppa))

    s_pkgs = get_published_sources(source, series)
    d_pkgs = get_published_sources(dest, series)

    for name, ver in s_pkgs.items():
        if args.package and args.package not in name:
            continue
        if name in d_pkgs and d_pkgs[name] != ver:
            print(f"{'[dry-run] ' if args.dry_run else ''}Copying on {series}: {name} ({d_pkgs.get(name, 'None')} -> {ver})")
            if not args.dry_run:
                dest.copyPackage(
                    source_name=name,
                    version=ver,
                    from_archive=source,
                    to_series=series,
                    to_pocket="Release",
                    include_binaries=True,
                )

if __name__ == "__main__":
    main()
        