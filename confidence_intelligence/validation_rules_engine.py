from pathlib import Path
import json

RULES_FILE = "validation_rules.json"
SUMMARY_FILE = "validation_rules_summary.txt"

rules = {
    "THRESHOLD": {
        "validation_days": 30,
        "benchmark": "REAL_THRESHOLD_90",
        "correct_if": "VIRTUAL_THRESHOLD_OUTPERFORMS_OR_CONFIRMS_KEEP_90",
        "status": "RULE_DEFINED"
    },
    "REGIONAL": {
        "validation_days": 30,
        "benchmark": "GLOBAL_MARKET_COMPARISON",
        "correct_if": "SELECTED_REGION_OUTPERFORMS_OTHER_REGIONS",
        "status": "RULE_DEFINED"
    },
    "SECTOR": {
        "validation_days": 30,
        "benchmark": "SPY",
        "correct_if": "SELECTED_SECTOR_OUTPERFORMS_SPY",
        "status": "RULE_DEFINED"
    },
    "MACRO": {
        "validation_days": 90,
        "benchmark": "SPY",
        "correct_if": "MACRO_BULLISH_AND_SPY_POSITIVE_OR_MACRO_BEARISH_AND_SPY_NEGATIVE",
        "status": "RULE_DEFINED"
    },
    "HORIZON": {
        "validation_days": 180,
        "benchmark": "REGIONAL_LONG_TERM_COMPARISON",
        "correct_if": "LONG_TERM_REGION_OUTPERFORMS_PEERS",
        "status": "RULE_DEFINED"
    }
}

Path(RULES_FILE).write_text(
    json.dumps(rules, indent=2)
)

summary = [
    "===== V22.3 VALIDATION RULES ENGINE =====",
    "",
    "Validation Rules Created:",
]

for vote, rule in rules.items():
    summary.append(
        f"{vote} | "
        f"{rule['validation_days']}d | "
        f"Benchmark {rule['benchmark']} | "
        f"{rule['status']}"
    )

summary.extend([
    "",
    "Protection:",
    "Outcome scoring will use explicit rules instead of guessing.",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(SUMMARY_FILE).write_text(text)

print(text)
