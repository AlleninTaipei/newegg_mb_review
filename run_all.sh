#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
    set -a; source .env; set +a
fi

run_pipeline() {
    local region=$1; shift
    for script in "$@"; do
        echo "[${region}] ${script} ..."
        if ! python3 "${script}"; then
            echo "[${region}] FAILED at ${script}" >&2
            return 1
        fi
    done
    echo "[${region}] all done"
}

run_pipeline "Newegg" scraper.py generate_dashboard.py send_email.py &
PID_NEWEGG=$!
run_pipeline "Kakaku" kakaku_scraper.py generate_kakaku_dashboard.py kakaku_send_email.py &
PID_KAKAKU=$!
run_pipeline "Danawa" danawa_scraper.py generate_danawa_dashboard.py danawa_send_email.py &
PID_DANAWA=$!

EXIT=0
for pid_region in "${PID_NEWEGG}:Newegg" "${PID_KAKAKU}:Kakaku" "${PID_DANAWA}:Danawa"; do
    pid="${pid_region%%:*}"; region="${pid_region##*:}"
    if ! wait "$pid"; then
        echo "[${region}] pipeline FAILED" >&2
        EXIT=1
    fi
done

exit $EXIT
