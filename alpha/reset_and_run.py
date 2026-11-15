"""
Reset script: clear the screener tables and re-run the pipeline.

ONLY for a brand-new or corrupted database. Once the initial load is complete the data is
protected and this refuses to run (see app/database/safety.py). To override on purpose, set
ALPHA_UNLOCK_DESTRUCTIVE=I-UNDERSTAND for that one command. The daily run never needs this: it
only adds, updates and soft-removes.
"""

from app.database.insert_daily import clear_all_tables


def run_pipeline():
    """Run the main pipeline to populate tables with correct data."""
    from app.main import run_system

    run_system()


if __name__ == "__main__":
    print("Clearing Supabase tables (blocked if the data is protected)...")
    clear_all_tables()
    print("\nRunning pipeline...")
    run_pipeline()
    print("\nDone!")
