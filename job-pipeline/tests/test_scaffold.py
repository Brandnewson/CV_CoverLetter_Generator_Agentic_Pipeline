"""Tests for project scaffold and structure."""

import importlib
import sys
from pathlib import Path


# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestProjectStructure:
    """Tests for verifying project scaffold exists correctly."""
    
    def test_required_directories_exist(self):
        """All required directories must exist."""
        required_dirs = [
            "discovery",
            "profile",
            "db",
            "tests",
            "dashboard",
        ]
        
        for dir_name in required_dirs:
            dir_path = PROJECT_ROOT / dir_name
            assert dir_path.exists(), f"Directory not found: {dir_name}"
            assert dir_path.is_dir(), f"Not a directory: {dir_name}"
    
    def test_required_files_exist(self):
        """All required files must exist."""
        required_files = [
            "discovery/__init__.py",
            "discovery/run_search.py",
            "discovery/dedup.py",
            "discovery/scorer.py",
            "discovery/config.yaml",
            "profile/master_bullets.md",
            "profile/experience.md",
            "profile/scoring_profile.yaml",
            "db/schema.sql",
            "tests/__init__.py",
            "dashboard/review.py",
            "setup_db.py",
            "README.md",
            ".env.example",
        ]
        
        for file_path in required_files:
            full_path = PROJECT_ROOT / file_path
            assert full_path.exists(), f"File not found: {file_path}"
            assert full_path.is_file(), f"Not a file: {file_path}"
    
    def test_env_example_has_required_keys(self):
        """The .env.example file must contain required keys."""
        env_path = PROJECT_ROOT / ".env.example"
        content = env_path.read_text()
        
        required_keys = ["DATABASE_URL", "OPENAI_API_KEY"]
        for key in required_keys:
            assert key in content, f".env.example missing key: {key}"
    
    def test_imports_resolve(self):
        """All module imports must resolve without error."""
        # Test discovery module imports
        from discovery import run_search
        from discovery import dedup
        from discovery import scorer
        
        # Verify key functions exist
        assert hasattr(run_search, 'run_search')
        assert hasattr(run_search, 'normalise_job')
        assert hasattr(run_search, 'insert_jobs')
        
        assert hasattr(dedup, 'find_fuzzy_duplicates')
        assert hasattr(dedup, 'mark_duplicates')
        
        assert hasattr(scorer, 'score_job')
        assert hasattr(scorer, 'apply_hard_filters')
        assert hasattr(scorer, 'score_pending_jobs')
    
    def test_schema_sql_valid(self):
        """The schema.sql file must contain expected table definitions."""
        schema_path = PROJECT_ROOT / "db" / "schema.sql"
        content = schema_path.read_text()
        
        required_tables = ["jobs", "job_status", "application_packs", "search_runs"]
        for table in required_tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in content, \
                f"Schema missing table definition: {table}"
    
    def test_config_yaml_valid(self):
        """The config.yaml file must be valid YAML with expected structure."""
        import yaml
        
        config_path = PROJECT_ROOT / "discovery" / "config.yaml"
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        assert "search" in config, "Config missing 'search' section"
        assert "search_terms" in config["search"], "Config missing search_terms"
        assert "site_name" in config["search"], "Config missing site_name"
        
    def test_scoring_profile_valid(self):
        """The scoring_profile.yaml file must be valid YAML with expected structure."""
        import yaml
        
        profile_path = PROJECT_ROOT / "profile" / "scoring_profile.yaml"
        with open(profile_path, "r") as f:
            profile = yaml.safe_load(f)
        
        required_keys = [
            "target_roles",
            "industries",
            "must_have_keywords",
            "nice_to_have_keywords",
            "core_strengths",
        ]
        
        for key in required_keys:
            assert key in profile, f"Scoring profile missing: {key}"
