"""
Pytest configuration and shared fixtures.

This file contains pytest fixtures that are shared across
multiple test modules in the integration and unit test suites.
"""
import os
import pytest
from supabase import create_client, Client
import psycopg2
from psycopg2.extensions import connection


@pytest.fixture(scope="session")
def celery_config():
    """
    Configure Celery for testing with eager mode.

    In eager mode, tasks execute synchronously instead of being
    sent to the broker, making tests deterministic and faster.
    """
    return {
        'task_always_eager': True,
        'task_eager_propagates': True,
    }


@pytest.fixture(scope="function", autouse=True)
def celery_eager_mode():
    """
    Enable Celery eager mode for all tests automatically.

    This makes validate_file.apply_async() execute synchronously,
    allowing tests to run without a background worker.
    """
    from src.agent.celery_app import celery_app

    # Store original config
    original_always_eager = celery_app.conf.task_always_eager
    original_eager_propagates = celery_app.conf.task_eager_propagates

    # Enable eager mode
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    yield

    # Restore original config
    celery_app.conf.task_always_eager = original_always_eager
    celery_app.conf.task_eager_propagates = original_eager_propagates


@pytest.fixture(scope="session")
def supabase_client() -> Client:
    """
    Create a Supabase client instance using environment variables.

    This fixture is scoped to the session level to reuse the same
    client instance across all tests within the test session, reducing
    connection overhead.

    Environment variables required:
        SUPABASE_URL: Your Supabase project URL (e.g., https://xxxxx.supabase.co)
        SUPABASE_KEY: Service role key or anon key from Supabase project settings

    Returns:
        Client: Configured Supabase client instance

    Raises:
        pytest.skip: If required environment variables are not set
    """
    url: str | None = os.environ.get("SUPABASE_URL")
    key: str | None = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        pytest.skip("SUPABASE_URL and SUPABASE_KEY must be configured in environment")

    return create_client(url, key)


@pytest.fixture(scope="session")
def db_connection():
    """
    Create a direct PostgreSQL connection to the local test database.

    This fixture provides a psycopg2 connection for tests that need
    to execute raw SQL or verify database schema directly.
    Useful for DB migration tests (e.g., T-020-DB).

    Yields None when the local database is not available (e.g. when running
    cloud-only tests with --no-deps), allowing tests that don't need the
    local DB to proceed normally.

    Environment variables:
        DATABASE_URL: PostgreSQL connection string (default: from docker-compose)
    """
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://user:password@db:5432/sfpm_db"
    )

    conn = None
    try:
        conn = psycopg2.connect(database_url, connect_timeout=3)
        conn.autocommit = False
    except Exception:
        pass  # DB not available; yield None so callers can skip gracefully

    yield conn

    if conn is not None:
        conn.close()


@pytest.fixture(scope="session")
def supabase_db_connection() -> connection:
    """
    Create a direct PostgreSQL connection to Supabase database.

    This fixture is specifically for performance tests that need bulk operations
    using raw SQL against the same database that Supabase client uses.

    Environment variables:
        SUPABASE_DATABASE_URL: PostgreSQL connection string to Supabase

    Returns:
        psycopg2.connection: Active database connection to Supabase

    Yields:
        connection: Connection object for test use

    Cleanup:
        Closes connection after test session ends

    Example:
        >>> def test_bulk_delete(supabase_db_connection):
        >>>     cursor = supabase_db_connection.cursor()
        >>>     cursor.execute("DELETE FROM blocks WHERE iso_code ILIKE %s", ("TEST-%",))
        >>>     supabase_db_connection.commit()
    """
    database_url = os.environ.get("SUPABASE_DATABASE_URL")

    if not database_url:
        pytest.skip("SUPABASE_DATABASE_URL must be configured for performance tests")

    conn = psycopg2.connect(database_url)
    conn.autocommit = True  # Auto-commit for cleanup operations

    yield conn

    conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database_schema(db_connection):
    """
    Create test prerequisites in the local database.

    The blocks table, block_status ENUM, and all columns are created by the SQL
    migrations in supabase/migrations/ — either automatically on fresh volumes
    (via docker-entrypoint-initdb.d) or on demand via `make migrate-local`.

    This fixture only creates what the migrations do NOT provide:
    - profiles table (planned for a future US, needed as FK reference in schema tests)
    - 1 test profile row (seed data for tests that INSERT blocks with created_by)

    Skips silently when local DB is not available (cloud-only test runs).
    """
    if db_connection is None:
        yield  # DB not available; cloud-only tests (supabase_client) can still run
        return

    cursor = db_connection.cursor()

    try:
        # profiles is a future-US table not yet in migrations.
        # Schema tests that INSERT blocks with created_by/updated_by FKs need it.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID,
                name TEXT,
                email TEXT,
                role TEXT,
                workshop_id UUID,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        cursor.execute("""
            INSERT INTO profiles (id, name, email, role)
            VALUES ('00000000-0000-0000-0000-000000000001', 'Test User', 'test@example.com', 'architect')
            ON CONFLICT (id) DO NOTHING;
        """)

        db_connection.commit()

    except Exception as e:
        db_connection.rollback()
        pytest.skip(f"Failed to setup test prerequisites: {e}")

    yield
