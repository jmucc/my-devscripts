#!/usr/bin/env python3

from asyncio import sleep
import subprocess
import sys

TOKEN = "<YOUR_TOKEN_HERE>"

USAGE = (
    "Usage: {prog} [--ip server-ip] [--series series] [--client-name client-name] [--account-name account-name] [--hostname hostname] [--ppas ppas] [--register register]\n"
    "\n"
    "Arguments:\n"
    "  server-ip               Landscape server IP (default: none)\n"
    "  series                  Ubuntu series to launch (default: noble)\n"
    "  client-name             LXC container name (default: client-test)\n"
    "  account-name            Landscape account name (default: standalone)\n"
    "  hostname                Hostname to set inside the container (default: none)\n"
    "  ppas                    Additional PPAs to add inside the container (default: none)\n"
    "  register                Whether to register to Landscape (default: true)\n"
    
)


def run(cmd, check=True):
    """Run a command, streaming output; return the CompletedProcess."""
    print(f"+ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def lxc_exec(name, script):
    """Run a bash script inside the named LXC container."""
    return run(["lxc", "exec", name, "--", "bash", "-c", script])


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(USAGE.format(prog=argv[0]))
        return 1

    serverip = None
    series = "noble"
    name = "client-test"
    account_name = "standalone"
    hostname = None
    ppas = None
    register = "true"

    idx = 1
    while idx < len(argv) and argv[idx].startswith("--"):
        if argv[idx] == "--series":
            series = argv[idx + 1]
            idx += 2
        elif argv[idx] == "--client-name":
            name = argv[idx + 1]
            idx += 2
        elif argv[idx] == "--account-name":
            account_name = argv[idx + 1]
            idx += 2
        elif argv[idx] == "--hostname":
            hostname = argv[idx + 1]
            idx += 2
        elif argv[idx] == "--ip":
            serverip = argv[idx + 1]
            idx += 2
        elif argv[idx] == "--ppas":
            ppas = argv[idx + 1]
            idx += 2
        elif argv[idx] == "--register":
            register = argv[idx + 1]
            idx += 2
        else:
            sys.stderr.write(f"Unknown option: {argv[idx]}\n")
            sys.stderr.write(USAGE.format(prog=argv[0]))
            return 1

    if not (serverip or hostname):
        sys.stderr.write("Error: either --ip or --hostname must be specified\n")
        sys.stderr.write(USAGE.format(prog=argv[0]))
        return 1

    # Recreate the container from scratch.
    subprocess.run(
        ["lxc", "delete", "--force", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    run(["lxc", "launch", f"ubuntu:{series}", name])

    # Let first-boot initialization finish so pro/apt/network are ready.
    lxc_exec(name, "cloud-init status --wait")

    print("Attaching Ubuntu Pro...")
    lxc_exec(
        name,
        '''
set -e
for i in 1 2 3 4 5; do
	if sudo pro attach {token} >/tmp/pro-attach.log 2>&1; then
		echo "Ubuntu Pro attached"
		exit 0
	fi

	if sudo pro status 2>/dev/null | grep -qi "attached"; then
		echo "Ubuntu Pro already attached"
		exit 0
	fi

	echo "pro attach attempt $i failed; retrying in 5s"
	sleep 5
done

echo "pro attach failed after retries"
cat /tmp/pro-attach.log
exit 1
'''.format(token=TOKEN),
    )

    if ppas:
        ppa_list = [p.strip() for p in ppas.split(",") if p.strip()]
        for position, ppa in enumerate(ppa_list):
            lxc_exec(name, f"sudo add-apt-repository -y ppa:{ppa}")

            # First PPA gets highest priority, each subsequent one lower.
            priority = 1000 - position
            owner, _, repo = ppa.partition("/")
            origin = f"LP-PPA-{owner}" + (f"-{repo}" if repo else "")
            pref_file = f"/etc/apt/preferences.d/ppa-{position}.pref"
            lxc_exec(
                name,
                f"""sudo tee {pref_file} >/dev/null <<EOF
Package: *
Pin: release o={origin}
Pin-Priority: {priority}
EOF""",
            )

    print("Installing landscape client...")
    lxc_exec(
        name,
        "sudo apt-get update && sudo apt-get install -y landscape-client openssl",
    )

    print("Fetching server certificate...")
    address = hostname or serverip
    if serverip and hostname:
        lxc_exec(name, f"echo \"{serverip} {hostname}\" | sudo tee -a /etc/hosts")

    lxc_exec(
        name,
        f"openssl s_client -connect {address}:443 -servername {address} "
        "</dev/null 2>/dev/null | openssl x509 -outform PEM | "
        "sudo tee /etc/landscape/server.pem >/dev/null",
    )
    lxc_exec(name, "grep -q 'BEGIN CERTIFICATE' /etc/landscape/server.pem")

    print("Writing /etc/landscape/client.conf...")
    lxc_exec(
        name,
        f"""sudo tee /etc/landscape/client.conf >/dev/null <<EOF
[client]
computer_title = {name}
account_name = {account_name}
url = https://{address}/message-system
ping_url = http://{address}/ping
ssl_public_key = /etc/landscape/server.pem
include_manager_plugins = ScriptExecution
script_users = ubuntu,landscape,root
EOF""",
    )

    if register.lower() != "true":
        print("Skipping landscape registration as per --register flag")
        return 0

    print("Running landscape-config --silent...")
    lxc_exec(name, "sudo landscape-config --silent")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
