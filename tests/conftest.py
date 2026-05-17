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

    CRITICAL: Also monkeypatches Celery.send_task() because it ignores
    task_always_eager. This ensures tasks sent via backend's send_task()
    are executed immediately with registered tasks from agent app.
    """
    from src.agent.celery_app import celery_app
    import infra.celery_client

    # Force import of tasks to register them (Celery doesn't auto-load in tests)
    try:
        from src.agent.tasks import file_validation, geometry_processing  # noqa: F401
    except ImportError:
        pass  # Some tests may not have access to agent tasks

    # Store original config for agent app
    original_always_eager = celery_app.conf.task_always_eager
    original_eager_propagates = celery_app.conf.task_eager_propagates

    # Enable eager mode for agent app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    # Store original send_task method
    from celery import Celery
    original_send_task = Celery.send_task

    def eager_send_task(self, name, args=None, kwargs=None, **options):
        """
        Monkeypatched send_task that executes tasks immediately.
        
        Because send_task() ignores task_always_eager, we intercept it
        and call the task directly if it's registered.
        """
        if name in celery_app.tasks:
            # Task is registered, execute it directly
            task = celery_app.tasks[name]
            return task.apply(args=args or [], kwargs=kwargs or {})
        else:
            # Task not registered, fall back to original behavior
            return original_send_task(self, name, args, kwargs, **options)

    # Apply monkeypatch
    Celery.send_task = eager_send_task

    # Also patch backend Celery client to use agent app (so tasks are registered)
    original_backend_client = infra.celery_client._celery_client
    infra.celery_client._celery_client = celery_app

    yield

    # Restore original send_task
    Celery.send_task = original_send_task

    # Restore original config for agent app
    celery_app.conf.task_always_eager = original_always_eager
    celery_app.conf.task_eager_propagates = original_eager_propagates

    # Restore backend client
    infra.celery_client._celery_client = original_backend_client


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


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_blocks(supabase_client: Client):
    """
    Clean up test blocks after each test to prevent duplicate key violations.

    This fixture automatically runs after each test function to delete
    any blocks with iso_codes that match common test patterns:
    - TEST-*
    - GLPER.B-PAE0720.*  (test fixtures)
    - GLPER.B-TEST.*

    Scope: function (runs per test)
    Autouse: True (runs automatically for all tests)
    """
    yield  # Let the test run first
    
    # Clean up test data after test completes
    try:
        # Delete blocks with test iso_codes
        test_patterns = [
            "TEST-%",
            "GLPER.B-PAE0720%",  # Test fixtures - cleanup re-enabled
            "GLPER.B-TEST%"
        ]
        
        for pattern in test_patterns:
            supabase_client.table("blocks").delete().ilike("iso_code", pattern).execute()
    except Exception:
        # Ignore cleanup errors (test data may not exist)
        pass


@pytest.fixture(scope="session")
def db_connection():
    """
    Create a direct PostgreSQL connection to the local test database.

    This fixture provides a psycopg2 connection for tests that need
    to execute raw SQL or verify database schema directly.
    Useful for DB migration tests (e.g., T-020-DB).

    Uses autocommit=True to prevent cascading transaction failures when
    one test aborts its transaction.

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
        conn.autocommit = True  # Prevent cascading transaction failures
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


@pytest.fixture(scope="session")
def test_3dm_file_in_storage(supabase_client: Client):
    """
    Upload test .3dm file to Supabase Storage for validation tests.

    This fixture ensures the test-model.3dm fixture exists in Supabase Storage
    at the path expected by validation integration tests.

    Scope: session (uploads once per test session)
    Cleanup: Deletes the test file after all tests complete

    Storage path: raw-uploads/test-fixtures/test-model.3dm

    Returns:
        str: The storage path of the uploaded file
    """
    from pathlib import Path
    
    BUCKET_NAME = "raw-uploads"
    DESTINATION_PATH = "test-fixtures/test-model.3dm"
    SOURCE_FILE = Path(__file__).parent / "fixtures" / "test-model.3dm"
    
    # Upload test file
    try:
        with open(SOURCE_FILE, 'rb') as file:
            supabase_client.storage.from_(BUCKET_NAME).upload(
                path=DESTINATION_PATH,
                file=file,
                file_options={"content-type": "application/octet-stream", "upsert": "true"}
            )
        print(f"✅ Test fixture uploaded to {BUCKET_NAME}/{DESTINATION_PATH}")
    except Exception as e:
        pytest.skip(f"Failed to upload test fixture: {e}")
    
    yield DESTINATION_PATH
    
    # Cleanup: Delete test file after session
    try:
        supabase_client.storage.from_(BUCKET_NAME).remove([DESTINATION_PATH])
        print(f"🧹 Test fixture cleaned up from storage")
    except Exception:
        pass  # Ignore cleanup errors


# ============================================================================
# T-1806 E2E LangGraph Integration Test Fixtures
# ============================================================================

@pytest.fixture
def mock_openai_responses():
    """
    Load mock OpenAI response fixtures from JSON files.
    
    Returns dict with keys:
        - hp_dovela_success: Successful classification response
        - timeout_error: Timeout error simulation
        - rate_limit_error: Rate limit error simulation
    
    Usage in tests:
        def test_something(mock_openai_responses):
            success_response = mock_openai_responses["hp_dovela_success"]
    """
    from pathlib import Path
    import json
    
    fixtures_dir = Path(__file__).parent / "fixtures" / "openai_responses"
    
    responses = {}
    for json_file in fixtures_dir.glob("*.json"):
        with open(json_file) as f:
            responses[json_file.stem] = json.load(f)
    
    return responses


@pytest.fixture
def mock_openai_client(monkeypatch, mock_openai_responses):
    """
    Mock OpenAI client for E2E tests to avoid consuming tokens.
    
    Factory fixture that allows configuring different response behaviors:
        - "success": Returns valid classification JSON (dovela, confidence 0.92)
        - "timeout": Raises TimeoutError after 3 retries
        - "rate_limit": Raises HTTP 429 rate limit error
    
    Usage:
        def test_hp_classification(mock_openai_client):
            mock_openai_client("success")
            # StateGraph will now receive mocked response
    
    Args:
        behavior (str): One of "success", "timeout", "rate_limit"
    
    Returns:
        Mock ChatOpenAI client configured with specified behavior
    """
    from unittest.mock import Mock
    from langchain_core.messages import AIMessage
    
    def _configure_mock(behavior: str = "success"):
        """Inner factory function to configure mock behavior."""
        
        from unittest.mock import Mock, MagicMock
        from langchain_core.messages import AIMessage
        import json
        
        # Create mock ChatOpenAI client
        mock_chat_openai = Mock()
        
        if behavior == "success":
            # Return valid classification JSON
            response_data = mock_openai_responses["hp_dovela_success"]
            content = response_data["choices"][0]["message"]["content"]
            
            # Mock LangChain ChatOpenAI.invoke() to return AIMessage
            mock_response = AIMessage(content=content)
            mock_chat_openai.invoke = Mock(return_value=mock_response)
            
        elif behavior == "timeout":
            # Simulate timeout
            from openai import APITimeoutError
            mock_chat_openai.invoke = Mock(side_effect=APITimeoutError("Request timeout after 10 seconds"))
            
        elif behavior == "rate_limit":
            # Simulate rate limit error
            from openai import RateLimitError
            mock_response = Mock(status_code=429)
            mock_chat_openai.invoke = Mock(
                side_effect=RateLimitError(
                    "Rate limit exceeded",
                    response=mock_response,
                    body={"error": {"message": "Rate limit exceeded"}}
                )
            )
        
        else:
            raise ValueError(f"Unknown mock behavior: {behavior}")
        
        # Monkeypatch ChatOpenAI instantiation in llm_client.py
        monkeypatch.setattr(
            "src.agent.graph.llm_client.ChatOpenAI",
            lambda **kwargs: mock_chat_openai
        )
        
        return mock_chat_openai
    
    return _configure_mock


@pytest.fixture
def e2e_upload_test_file(supabase_client: Client):
    """
    Helper fixture to upload .3dm test files to Supabase Storage for E2E tests.
    
    Factory fixture that uploads a file and returns its storage path.
    Automatically cleans up uploaded files after test completes.
    
    Usage:
        def test_something(e2e_upload_test_file):
            storage_path = e2e_upload_test_file("test-model.3dm", "SF-C12-D-001.3dm")
            # File is now at raw-uploads/test-e2e/SF-C12-D-001.3dm
    
    Args:
        source_filename (str): Filename in tests/fixtures/
        destination_filename (str): Filename to use in Storage (for nomenclature testing)
    
    Returns:
        str: Storage path (e.g., "test-e2e/SF-C12-D-001.3dm")
    """
    from pathlib import Path
    
    uploaded_files = []
    
    def _upload_file(source_filename: str, destination_filename: str) -> str:
        """Upload a test file and track for cleanup."""
        BUCKET_NAME = "raw-uploads"
        DESTINATION_PATH = f"test-e2e/{destination_filename}"
        SOURCE_FILE = Path(__file__).parent / "fixtures" / source_filename
        
        if not SOURCE_FILE.exists():
            raise FileNotFoundError(f"Test fixture not found: {SOURCE_FILE}")
        
        # Upload to Supabase Storage
        try:
            with open(SOURCE_FILE, 'rb') as file:
                supabase_client.storage.from_(BUCKET_NAME).upload(
                    path=DESTINATION_PATH,
                    file=file,
                    file_options={"content-type": "application/octet-stream", "upsert": "true"}
                )
            uploaded_files.append(DESTINATION_PATH)
            return DESTINATION_PATH
            
        except Exception as e:
            pytest.fail(f"Failed to upload test file {source_filename}: {e}")
    
    yield _upload_file
    
    # Cleanup: Delete all uploaded files
    if uploaded_files:
        try:
            supabase_client.storage.from_("raw-uploads").remove(uploaded_files)
        except Exception:
            pass  # Ignore cleanup errors


@pytest.fixture
def e2e_cleanup_blocks(supabase_client: Client):
    """
    Cleanup fixture for E2E test blocks with specific iso_code patterns.
    
    Deletes blocks created during E2E tests to prevent test pollution.
    Tracks block_ids created during test and deletes them after test completes.
    
    Usage:
        def test_e2e_flow(e2e_cleanup_blocks):
            block_id = create_test_block()
            e2e_cleanup_blocks.track(block_id)
            # Block will be deleted after test
    
    Yields:
        Cleanup helper with methods:
            - track(block_id: str): Add block_id to cleanup list
            - cleanup_now(): Manually trigger cleanup (useful for debugging)
    """
    tracked_block_ids = []
    
    class CleanupHelper:
        def track(self, block_id: str):
            """Track a block_id for cleanup."""
            tracked_block_ids.append(block_id)
        
        def cleanup_now(self):
            """Manually trigger cleanup (for debugging)."""
            if tracked_block_ids:
                try:
                    supabase_client.table("blocks").delete().in_("id", tracked_block_ids).execute()
                except Exception as e:
                    print(f"Warning: Failed to cleanup blocks: {e}")
    
    helper = CleanupHelper()
    
    yield helper
    
    # Auto-cleanup after test
    helper.cleanup_now()
