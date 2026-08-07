#!/usr/bin/env bash
# studio-site-from-host: guarantee a known local admin login.
#
# Importing the source database replaces wp_users, so the credentials Studio generated at
# setup no longer work and the imported accounts' passwords are unknown. This sets a
# predictable local login: it updates the password if the account already exists, and
# creates it otherwise.
#
# LOCAL ONLY. This runs through `studio wp` against the Studio site directory and never
# touches the hosted site. A trivial password is deliberate for a throwaway local mirror -
# do not reuse this script against anything reachable from outside the machine.
#
# Usage:
#   ensure-admin-user.sh --target-dir <site-root> [--username admin] [--password admin] [--email <addr>]

set -euo pipefail

usage() {
  cat <<EOF
Usage: ensure-admin-user.sh --target-dir <site-root> [--username admin] [--password admin] [--email <addr>]

  --target-dir  Studio site root (the directory containing wp-content/).
  --username    Login to ensure. Default 'admin'.
  --password    Password to set. Default 'admin'.
  --email       Email used only when the account has to be created.
                Default '<username>@localhost.com'.

  -h, --help    Show this help.

On success prints a machine-readable block on stdout:
  RESULT_ACTION=created|updated
  RESULT_USERNAME=<login>
  RESULT_PASSWORD=<password>

Requires: studio (Studio CLI) on PATH, with the site already registered.
EOF
}

target=""
username="admin"
password="admin"
email=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir)
      [[ $# -ge 2 ]] || { echo "ensure-admin-user.sh: --target-dir needs a value" >&2; exit 2; }
      target="$2"; shift 2 ;;
    --username)
      [[ $# -ge 2 ]] || { echo "ensure-admin-user.sh: --username needs a value" >&2; exit 2; }
      username="$2"; shift 2 ;;
    --password)
      [[ $# -ge 2 ]] || { echo "ensure-admin-user.sh: --password needs a value" >&2; exit 2; }
      password="$2"; shift 2 ;;
    --email)
      [[ $# -ge 2 ]] || { echo "ensure-admin-user.sh: --email needs a value" >&2; exit 2; }
      email="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ensure-admin-user.sh: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$target" ]]; then
  echo "ensure-admin-user.sh: --target-dir is required" >&2
  usage >&2
  exit 2
fi

[[ -n "$username" ]] || { echo "ensure-admin-user.sh: --username cannot be empty" >&2; exit 2; }
[[ -n "$password" ]] || { echo "ensure-admin-user.sh: --password cannot be empty" >&2; exit 2; }
[[ -n "$email" ]] || email="${username}@localhost.com"

command -v studio >/dev/null 2>&1 || {
  echo "ensure-admin-user.sh: 'studio' CLI not found on PATH." >&2
  exit 1
}

case "$target" in
  /*) abs_target="$target" ;;
  *)  abs_target="$PWD/$target" ;;
esac

if [[ ! -d "$abs_target/wp-content" ]]; then
  echo "ensure-admin-user.sh: $abs_target/wp-content does not exist; is this a WordPress site?" >&2
  exit 1
fi

# `wp user get` exits non-zero when the login does not exist, which is the existence check.
if studio wp --path "$abs_target" user get "$username" --field=ID >/dev/null 2>&1; then
  echo "==> '$username' exists; setting its password and ensuring the administrator role"
  studio wp --path "$abs_target" user update "$username" --user_pass="$password" --role=administrator --skip-email >&2
  action="updated"
else
  echo "==> creating '$username' as an administrator"
  # No --send-email flag, so WordPress does not mail the new account.
  studio wp --path "$abs_target" user create "$username" "$email" --role=administrator --user_pass="$password" >&2
  action="created"
fi

echo
echo "RESULT_ACTION=$action"
echo "RESULT_USERNAME=$username"
echo "RESULT_PASSWORD=$password"
