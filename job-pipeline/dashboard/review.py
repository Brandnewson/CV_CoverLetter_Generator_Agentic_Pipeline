"""Review dashboard for viewing and managing job shortlist."""

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from tabulate import tabulate


def get_top_jobs(conn, limit: int = 20) -> list[dict]:
    """
    Query top jobs by fit_score where status is 'new' and discovered recently.
    
    Args:
        conn: Database connection
        limit: Maximum number of jobs to return
        
    Returns:
        List of job dictionaries with status info
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                j.id,
                js.fit_score,
                j.company,
                j.title,
                j.location,
                j.source,
                j.job_url,
                js.fit_summary,
                j.salary_min,
                j.salary_max
            FROM jobs j
            JOIN job_status js ON js.job_id = j.id
            WHERE js.status = 'new'
              AND j.date_discovered > NOW() - INTERVAL '48 hours'
              AND j.is_duplicate = FALSE
              AND js.fit_score IS NOT NULL
            ORDER BY js.fit_score DESC
            LIMIT %s
        """, (limit,))
        
        columns = ["id", "fit_score", "company", "title", "location", 
                   "source", "job_url", "fit_summary", "salary_min", "salary_max"]
        
        jobs = []
        for row in cur.fetchall():
            jobs.append(dict(zip(columns, row)))
        
        return jobs


def mark_job_queued(conn, job_id: int) -> bool:
    """
    Mark a job as 'queued' for document generation.
    
    Args:
        conn: Database connection
        job_id: ID of the job to mark
        
    Returns:
        True if job was updated, False if job not found
    """
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE job_status
            SET status = 'queued', status_updated = NOW()
            WHERE job_id = %s
            RETURNING job_id
        """, (job_id,))
        
        result = cur.fetchone()
        conn.commit()
        
        return result is not None


def truncate_url(url: str, max_length: int = 40) -> str:
    """Truncate URL to specified length."""
    if not url:
        return ""
    if len(url) <= max_length:
        return url
    return url[:max_length - 3] + "..."


def format_salary(salary_min: int | None, salary_max: int | None) -> str:
    """Format salary range for display."""
    if salary_min and salary_max:
        return f"£{salary_min:,}-{salary_max:,}"
    elif salary_max:
        return f"Up to £{salary_max:,}"
    elif salary_min:
        return f"From £{salary_min:,}"
    return "Not stated"


def display_jobs(jobs: list[dict]) -> None:
    """Display jobs in a formatted table."""
    if not jobs:
        print("\nNo jobs found matching criteria.")
        print("Try running discovery/run_search.py first, or check your filters.")
        return
    
    print(f"\n{'=' * 80}")
    print(f"TOP {len(jobs)} NEW JOBS (Last 48 hours)")
    print(f"{'=' * 80}\n")
    
    # Prepare table data
    table_data = []
    for job in jobs:
        score = job["fit_score"]
        score_str = f"{score:.2f}" if score is not None else "N/A"
        
        table_data.append([
            job["id"],
            score_str,
            job["company"][:25] if job["company"] else "",
            job["title"][:35] if job["title"] else "",
            job["location"][:20] if job["location"] else "",
            job["source"],
        ])
    
    headers = ["ID", "Score", "Company", "Title", "Location", "Source"]
    print(tabulate(table_data, headers=headers, tablefmt="simple"))
    
    # Print detailed summaries
    print(f"\n{'-' * 80}")
    print("DETAILED FIT SUMMARIES")
    print(f"{'-' * 80}\n")
    
    for job in jobs:
        print(f"[{job['id']}] {job['company']} — {job['title']}")
        print(f"     Score: {job['fit_score']:.2f} | {job['location'] or 'Location not specified'}")
        print(f"     Salary: {format_salary(job['salary_min'], job['salary_max'])}")
        if job["fit_summary"]:
            summary = job["fit_summary"][:150] + "..." if len(job["fit_summary"] or "") > 150 else job["fit_summary"]
            print(f"     {summary}")
        print(f"     URL: {truncate_url(job['job_url'], 60)}")
        print()


def main() -> None:
    """Main entry point for the review dashboard."""
    # Load environment
    load_dotenv(Path(__file__).parent.parent / ".env")
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return
    
    try:
        conn = psycopg2.connect(db_url)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        return
    
    try:
        # Display jobs
        jobs = get_top_jobs(conn, limit=20)
        display_jobs(jobs)
        
        if not jobs:
            return
        
        # Interactive prompt
        while True:
            print("-" * 40)
            user_input = input("Enter job ID to mark as queued (or 'q' to quit): ").strip()
            
            if user_input.lower() == 'q':
                print("Goodbye!")
                break
            
            try:
                job_id = int(user_input)
                
                # Verify job exists in our list
                job_ids = [j["id"] for j in jobs]
                if job_id not in job_ids:
                    print(f"Job ID {job_id} not in current list. Enter a valid ID or 'q' to quit.")
                    continue
                
                if mark_job_queued(conn, job_id):
                    job = next(j for j in jobs if j["id"] == job_id)
                    print(f"✓ Marked job {job_id} ({job['company']} - {job['title']}) as 'queued'")
                else:
                    print(f"Could not find job with ID {job_id}")
                    
            except ValueError:
                print("Please enter a valid job ID number or 'q' to quit.")
                
    finally:
        conn.close()


if __name__ == "__main__":
    main()
