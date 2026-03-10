"""API cost reporting tool."""

import json
from pathlib import Path
from datetime import datetime


# Haiku pricing (per 1M tokens)
HAIKU_INPUT_PRICE = 0.25  # $0.25 per 1M input tokens
HAIKU_OUTPUT_PRICE = 1.25  # $1.25 per 1M output tokens
TOTAL_BUDGET = 50.00


def load_usage_log(log_path: Path, user_id: int = 1) -> list[dict]:
    """Load API usage entries from JSONL file filtered by user_id."""
    if not log_path.exists():
        return []
    
    entries = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                if entry.get('user_id', 1) == user_id:
                    entries.append(entry)
    return entries


def calculate_cost(entries: list[dict]) -> dict:
    """Calculate cost breakdown from usage entries."""
    total_input = sum(e.get('input_tokens', 0) for e in entries)
    total_output = sum(e.get('output_tokens', 0) for e in entries)
    total_calls = len(entries)
    
    input_cost = (total_input / 1_000_000) * HAIKU_INPUT_PRICE
    output_cost = (total_output / 1_000_000) * HAIKU_OUTPUT_PRICE
    total_cost = input_cost + output_cost
    
    return {
        'calls': total_calls,
        'input_tokens': total_input,
        'output_tokens': total_output,
        'total_cost': total_cost,
        'budget_remaining': TOTAL_BUDGET - total_cost
    }


def print_report(user_id: int = 1) -> None:
    """Print formatted cost report."""
    log_path = Path(__file__).parent.parent / "logs" / "api_usage.jsonl"
    entries = load_usage_log(log_path, user_id)
    stats = calculate_cost(entries)
    
    print("""
API Usage Report
================
Model           Calls   Tokens In   Tokens Out   Est. Cost
──────────────────────────────────────────────────────────""")
    print(f"haiku-4-5     {stats['calls']:>6}   {stats['input_tokens']:>9}   {stats['output_tokens']:>10}   ${stats['total_cost']:.3f}")
    print("──────────────────────────────────────────────────────────")
    print(f"This session:                                        ${stats['total_cost']:.3f}")
    print(f"All time:                                            ${stats['total_cost']:.3f}")
    print(f"Budget remaining: ${stats['budget_remaining']:.2f} of ${TOTAL_BUDGET:.2f}")
    
    if stats['budget_remaining'] < 10:
        print("\n⚠ WARNING: remaining budget below $10")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Show API cost report")
    parser.add_argument("--user-id", type=int, default=1, help="User ID (default: 1)")
    args = parser.parse_args()
    print_report(args.user_id)
