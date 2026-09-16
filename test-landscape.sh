#!/bin/bash

# landscape-test.sh

usage() {
    cat <<'EOF'
Usage: landscape-test.sh [options]

Options:
  --series <series>   Ubuntu series to launch (default: noble)
  --ppas <list>       Comma-separated PPA list without the ppa: prefix
                      (default: landscape/self-hosted-beta)
  --name <name>       LXC container name (default: landscape-test)
  --full              Install recommended packages (default: false)
  --vm                Use the --vm option when launching the LXC container
  --memory            Memory to use (e.g. 8GiB). Only for use with --vm
  -h, --help          Show this help message

Positional arguments are still supported in this order:
  [series] [ppas] [name]
EOF
}

series="noble"
ppas="landscape/self-hosted-24.04"
name="test-landscape"
full_install=false
vm=false
memory=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --series)
            series="$2"
            shift 2
            ;;
        --ppas)
            ppas="$2"
            shift 2
            ;;
        --name)
            name="$2"
            shift 2
            ;;
        --full)
            full_install=true
            shift
            ;;
        --vm)
            vm=true
            shift
            ;;
        --memory)
            memory="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "$vm" && -n "$memory" ]]; then
    echo "Cannot supply memory without vm"
    exit 1
fi

if [[ "$full_install" == true ]]; then
    recommends=""
else
    recommends="--no-install-recommends"
fi

IFS=',' read -ra ppa_array <<< "$ppas"
OPTIONS=""

if [[ "$vm" == true ]]; then
    OPTIONS="${OPTIONS}--vm "
    if [[ -n "$memory" ]]; then
      OPTIONS="${OPTIONS}-c limits.memory=${memory}"
    fi
fi

lxc delete --force "$name"
lxc launch $OPTIONS "ubuntu:$series" "$name"
if [[ "$vm" == true ]]; then
  sleep 20 # VMs can take a while to launch
fi
lxc exec "$name" -- bash -c "sudo apt-get update && sudo apt-get install -y software-properties-common"
for ppa in "${ppa_array[@]}"; do
    lxc exec "$name" -- bash -c "sudo add-apt-repository -y ppa:$ppa"
done
lxc exec "$name" -- bash -c "sudo apt-get update"
lxc exec "$name" -- bash -c "sudo DEBIAN_FRONTEND=noninteractive apt-get install $recommends -y landscape-server-quickstart"
