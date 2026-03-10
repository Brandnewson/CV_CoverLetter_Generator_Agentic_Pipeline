"""Verify Phase 2 database schema."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    
    # Check tables exist
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' ORDER BY table_name
    """)
    tables = [r[0] for r in cur.fetchall()]
    print('Tables:', tables)
    
    # Check cv_sessions columns
    cur.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = 'cv_sessions' ORDER BY ordinal_position
    """)
    print('\ncv_sessions columns:')
    for col, dtype in cur.fetchall():
        print(f'  {col}: {dtype}')
    
    # Check cv_feedback columns
    cur.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = 'cv_feedback' ORDER BY ordinal_position
    """)
    print('\ncv_feedback columns:')
    for col, dtype in cur.fetchall():
        print(f'  {col}: {dtype}')
    
    # Check user_id on jobs
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'jobs' AND column_name = 'user_id'
    """)
    print('\njobs.user_id exists:', cur.fetchone() is not None)
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
