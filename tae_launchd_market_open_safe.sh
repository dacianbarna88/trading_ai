#!/bin/bash
# TAE LaunchAgent-safe market-open launcher (macOS TCC / Desktop path).
# Infrastructure only — does not modify trading or DPE logic.
#
# Invoked by: com.tradingai.market-open LaunchAgent via /bin/bash only.
# Avoids venv/bin/python3 as the launchd ProgramArguments executable.

set -uo pipefail

PROJECT_DIR="/Users/book/Desktop/trading_ai"
LOG_FILE="${PROJECT_DIR}/tae_launchd_market_open_safe.log"
ERR_FILE="${PROJECT_DIR}/tae_launchd_market_open_safe.err.log"
FRAMEWORK_PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
FALLBACK_PYTHON="/usr/bin/python3"

mkdir -p "${PROJECT_DIR}"

_ts() {
    date "+%Y-%m-%d %H:%M:%S %z"
}

_log() {
    echo "[$(_ts)] $*" | tee -a "${LOG_FILE}"
}

_log_err() {
    echo "[$(_ts)] $*" | tee -a "${ERR_FILE}" >&2
}

_run() {
    local label="$1"
    shift
    _log "CMD [${label}]: $*"
    "$@" >> "${LOG_FILE}" 2>> "${ERR_FILE}"
    local ec=$?
    _log "EXIT_CODE [${label}]: ${ec}"
    return "${ec}"
}

_pgrep_lines() {
    pgrep -fl "$1" 2>/dev/null | while read -r line; do
        case "$1" in
            live_bot.py)
                echo "$line" | grep -F "live_bot.py" | grep -v pgrep || true
                ;;
            *)
                echo "$line" | grep -F "$1" | grep -v pgrep || true
                ;;
        esac
    done
}

_pgrep_count() {
    local pattern="$1"
    local count=0
    local line
    while IFS= read -r line; do
        [ -n "$line" ] && count=$((count + 1))
    done < <(_pgrep_lines "$pattern")
    echo "${count}"
}

_bot_count() {
    _pgrep_count "live_bot.py"
}

_dashboard_count() {
    _pgrep_count "streamlit run dashboard_v2.py"
}

_resolve_python() {
    if [ -x "${FRAMEWORK_PYTHON}" ]; then
        echo "${FRAMEWORK_PYTHON}"
        return 0
    fi
    if [ -x "${FALLBACK_PYTHON}" ]; then
        _log "WARN: framework python missing — fallback ${FALLBACK_PYTHON}"
        echo "${FALLBACK_PYTHON}"
        return 0
    fi
    return 1
}

_main() {
    {
        echo ""
        echo "===== TAE LAUNCHD MARKET OPEN SAFE ====="
        echo "Started: $(_ts)"
        echo "Shell PID: $$ PPID: ${PPID:-unknown}"
    } >> "${LOG_FILE}"

    cd "${PROJECT_DIR}" || {
        _log_err "FATAL: cannot cd ${PROJECT_DIR}"
        return 78
    }

    export PATH="/Library/Frameworks/Python.framework/Versions/3.14/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    export TAE_SCHEDULER_SOURCE=launchd

    PYTHON_BIN="$(_resolve_python)" || {
        _log_err "FATAL: no usable python3 found"
        return 78
    }

    _log "whoami=$(whoami)"
    _log "pwd=$(pwd)"
    _log "date=$(_ts)"
    _log "TAE_SCHEDULER_SOURCE=${TAE_SCHEDULER_SOURCE}"
    _log "PATH=${PATH}"
    _log "PYTHON_BIN=${PYTHON_BIN}"
    _log "python_version=$("${PYTHON_BIN}" --version 2>&1)"
    _log "python_xattr=$({ xattr -l "${PYTHON_BIN}"; } 2>&1 || true)"
    _log "venv_xattr=$({ xattr -l "${PROJECT_DIR}/venv/bin/python3"; } 2>&1 || true)"
    _log "script_xattr=$({ xattr -l "${BASH_SOURCE[0]:-${0}}"; } 2>&1 || true)"
    _log "pre_run bot_count=$(_bot_count) dashboard_count=$(_dashboard_count)"

    local ec=0
    local phase_ec=0

    _log "[1/5] Awake guard"
    if [ -x "${PROJECT_DIR}/awake_guard.sh" ]; then
        _run "awake_guard" /bin/bash "${PROJECT_DIR}/awake_guard.sh" || phase_ec=$?
        if [ "${phase_ec}" -ne 0 ]; then
            _log_err "WARN: awake_guard exited ${phase_ec} — continuing"
        fi
    else
        _log_err "WARN: awake_guard.sh missing — skipping"
    fi

    _log "[2/5] Start bot via bot_controller.py (--force for scheduled launchd)"
    local bots_before
    bots_before=$(_bot_count)
    if [ "${bots_before}" -gt 1 ]; then
        _log_err "WARN: duplicate live_bot detected count=${bots_before} — not starting another"
    elif [ "${bots_before}" -eq 1 ]; then
        _log "SKIP: live_bot.py already running (count=1)"
    else
        _run "bot_controller_start" "${PYTHON_BIN}" "${PROJECT_DIR}/bot_controller.py" start --force || phase_ec=$?
        if [ "${phase_ec}" -ne 0 ]; then
            _log_err "ERROR: bot_controller start failed exit=${phase_ec}"
            ec=${phase_ec}
        fi
    fi

    _log "[3/5] Start dashboard via bot_controller.py (--force for scheduled launchd)"
    local dash_before
    dash_before=$(_dashboard_count)
    if [ "${dash_before}" -gt 1 ]; then
        _log_err "WARN: duplicate dashboard detected count=${dash_before} — not starting another"
    elif [ "${dash_before}" -ge 1 ]; then
        _log "SKIP: dashboard already running (count=${dash_before})"
    else
        _run "bot_controller_dashboard" "${PYTHON_BIN}" "${PROJECT_DIR}/bot_controller.py" start-dashboard --force || phase_ec=$?
        if [ "${phase_ec}" -ne 0 ]; then
            _log_err "ERROR: bot_controller start-dashboard failed exit=${phase_ec}"
            if [ "${ec}" -eq 0 ]; then
                ec=${phase_ec}
            fi
        fi
    fi

    _log "[4/5] Optional intelligence stack (non-fatal, framework python — NOT market_open_runner.sh)"
    if ! pgrep -f "tae_market_open_intelligence_runner.py" >/dev/null 2>&1; then
        _run "market_open_intelligence" "${PYTHON_BIN}" "${PROJECT_DIR}/tae_market_open_intelligence_runner.py" || {
            _log_err "WARN: intelligence runner non-zero — bot/dashboard unaffected"
        }
    else
        _log "SKIP: tae_market_open_intelligence_runner.py already running"
    fi

    if [ -f "${PROJECT_DIR}/morning_update.py" ]; then
        _run "morning_update" "${PYTHON_BIN}" "${PROJECT_DIR}/morning_update.py" || {
            _log_err "WARN: morning_update non-zero — continuing"
        }
    fi

    if [ -f "${PROJECT_DIR}/daily_intelligence_runner.py" ]; then
        _run "daily_intelligence" "${PYTHON_BIN}" "${PROJECT_DIR}/daily_intelligence_runner.py" || {
            _log_err "WARN: daily_intelligence_runner non-zero — continuing"
        }
    fi

    if [ -f "${PROJECT_DIR}/market_session_guard.py" ]; then
        _run "market_session_guard" "${PYTHON_BIN}" "${PROJECT_DIR}/market_session_guard.py" || {
            _log_err "WARN: market_session_guard non-zero — continuing"
        }
    fi

    _log "[5/5] Post-run status"
    local bot_count dash_count
    bot_count=$(_bot_count)
    dash_count=$(_dashboard_count)
    _log "post_run bot_count=${bot_count} dashboard_count=${dash_count}"

    if [ -f "${PROJECT_DIR}/bot_status.txt" ]; then
        _log "bot_status=$(cat "${PROJECT_DIR}/bot_status.txt" 2>/dev/null || echo MISSING)"
    fi
    if [ -f "${PROJECT_DIR}/dashboard_status.txt" ]; then
        _log "dashboard_status=$(cat "${PROJECT_DIR}/dashboard_status.txt" 2>/dev/null || echo MISSING)"
    fi
    if [ -f "${PROJECT_DIR}/bot_pid.txt" ]; then
        _log "bot_pid=$(cat "${PROJECT_DIR}/bot_pid.txt" 2>/dev/null || echo MISSING)"
    fi
    if [ -f "${PROJECT_DIR}/dashboard_pid.txt" ]; then
        _log "dashboard_pid=$(cat "${PROJECT_DIR}/dashboard_pid.txt" 2>/dev/null || echo MISSING)"
    fi

    _log "pgrep live_bot: $(pgrep -fl live_bot.py 2>/dev/null || echo none)"
    _log "pgrep dashboard: $(pgrep -fl 'streamlit run dashboard_v2.py' 2>/dev/null || echo none)"

    if [ "${bot_count}" -gt 1 ]; then
        _log_err "FAIL: duplicate live_bot count=${bot_count}"
        return 78
    fi
    if [ "${bot_count}" -lt 1 ]; then
        _log_err "FAIL: live_bot not running after launch"
        return 78
    fi
    if [ "${dash_count}" -lt 1 ]; then
        _log_err "FAIL: dashboard not running after launch"
        return 78
    fi

    _log "RESULT: PASS — bot and dashboard running, no duplicate bot"
    _log "Finished: $(_ts)"
    _log "===== END TAE LAUNCHD MARKET OPEN SAFE ====="
    return 0
}

_main
exit $?
