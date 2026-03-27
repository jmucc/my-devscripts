"""Copy published updated package versions over outdated package versions within a PPA.

Usage:
    python3 ppa-copy.py <user>/<ppa>

Example:
    python3 ppa-update.py landscape/self-hosted-beta
"""

import argparse
import os

from dataclasses import dataclass
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

@dataclass
class SeriesUpdate:
    package_name: str
    outdated_series: str
    latest_series: str
    outdated_version: str
    latest_version: str

def get_series_updates_by_package(ppa, series_filter=None, package_filter=None):
    series_updates = []
    name_to_latest_package = {}
    sorted_srcs = sorted(ppa.getPublishedSources(status="Published"), key=lambda src: src.date_published, reverse=True)
    for src in sorted_srcs:
        if package_filter and package_filter not in src.source_package_name:
            continue
        name = src.source_package_name
        if name not in name_to_latest_package:
            name_to_latest_package[name] = src
        else:
            latest_package = name_to_latest_package[name]

            series = src.distro_series_link.split("/")[-1]
            latest_series = latest_package.distro_series_link.split("/")[-1]

            ver = src.source_package_version.split("-")[0]
            latest_ver = latest_package.source_package_version.split("-")[0]

            if series_filter and (series not in series_filter or latest_series not in series_filter):
                continue

            if (
                series != latest_series and
                ver != latest_ver
            ):
                series_updates.append(
                    SeriesUpdate(
                        name,
                        series, 
                        latest_series,
                        src.source_package_version,
                        latest_package.source_package_version
                    ))

    return series_updates


def main():
    parser = argparse.ArgumentParser(
        description="Copy published updated package versions over outdated package versions within a PPA"
    )
    parser.add_argument(
        "ppa",
        type=parse_ppa_ref,
        help="PPA as user/ppa",
    )
    parser.add_argument(
        "--series",
        nargs="+",
        metavar="SERIES",
        help="Limit to one or more Ubuntu series (e.g. --series focal noble)",
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

    user, ppa = args.ppa

    ppa = lp.load(ppa_api_url(user, ppa))

    series_updates = get_series_updates_by_package(ppa, series_filter=args.series, package_filter=args.package)

    for update in series_updates:
        print(f"{'[dry-run] ' if args.dry_run else ''}Copying: {update.package_name} {update.latest_series} -> {update.outdated_series} ({update.outdated_version} -> {update.latest_version})")
        if not args.dry_run:
            ppa.copyPackage(
                source_name=update.package_name,
                version=update.latest_version,
                from_archive=ppa,
                to_series=update.outdated_series,
                to_pocket="Release",
                include_binaries=True,
            )

if __name__ == "__main__":
    main()
        