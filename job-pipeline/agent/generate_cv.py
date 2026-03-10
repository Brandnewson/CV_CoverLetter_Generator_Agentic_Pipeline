"""Main entry point for CV generation pipeline."""

import argparse
from pathlib import Path


def generate_cv(job_id: int, user_id: int = 1, check_only: bool = False) -> None:
    """
    Generate a CV for a specific job.
    
    Args:
        job_id: The database ID of the job to generate CV for
        user_id: User ID (default 1 for V1)
        check_only: If True, only validate prerequisites without generating
    """
    # Placeholder - will be implemented in Phase 12
    raise NotImplementedError("CV generation not yet implemented")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a tailored CV for a job")
    parser.add_argument("--job-id", required=True, type=int, help="Job ID from database")
    parser.add_argument("--user-id", type=int, default=1, help="User ID (default: 1)")
    parser.add_argument("--check", action="store_true", help="Only check prerequisites")
    args = parser.parse_args()
    generate_cv(args.job_id, args.user_id, args.check)
