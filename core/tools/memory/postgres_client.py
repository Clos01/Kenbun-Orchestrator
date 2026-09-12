import logging

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

import socket
import time
from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

_circuit_open_until = 0.0
_circuit_cooldown_seconds = 300.0  # 5 minutes backoff
_circuit_last_error = ""

def _probe_tcp(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False

def reset_postgres_circuit():
    """Resets the circuit breaker cooldown to immediately permit fresh connection attempts."""
    global _circuit_open_until, _circuit_last_error
    _circuit_open_until = 0.0
    _circuit_last_error = ""

def get_connection():
    """Returns a synchronous psycopg connection or fast-fails if in circuit cooldown."""
    global _circuit_open_until, _circuit_last_error
    if psycopg is None:
        raise RuntimeError("psycopg is not installed in current environment")

    now = time.time()
    if now < _circuit_open_until:
        remaining = int(_circuit_open_until - now)
        raise RuntimeError(
            f"PostgreSQL circuit breaker active ({remaining}s remaining in cooldown; last failure: {_circuit_last_error})"
        )

    host = getattr(settings, "POSTGRES_HOST", None)
    port = getattr(settings, "POSTGRES_PORT", 5432)
    if not host or not _probe_tcp(host, port, timeout=0.3):
        _circuit_open_until = now + _circuit_cooldown_seconds
        _circuit_last_error = f"Host {host}:{port} unreachable"
        raise RuntimeError(f"PostgreSQL host {host}:{port} unreachable. Fast-failing to local SQLite.")

    conn_str = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{host}:{port}/{settings.POSTGRES_DB}?connect_timeout=2"
    try:
        conn = psycopg.connect(conn_str, row_factory=dict_row)
        _circuit_open_until = 0.0
        _circuit_last_error = ""
        return conn
    except Exception as exc:
        _circuit_open_until = now + _circuit_cooldown_seconds
        _circuit_last_error = str(exc)
        raise exc

def init_db():
    """Initializes the PostgreSQL schemas if they do not exist."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. bayesian_weights
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bayesian_weights (
                        tool_id VARCHAR(255) NOT NULL,
                        category VARCHAR(255) NOT NULL DEFAULT 'global',
                        alpha FLOAT NOT NULL DEFAULT 1.0,
                        beta FLOAT NOT NULL DEFAULT 1.0,
                        success_count INTEGER NOT NULL DEFAULT 0,
                        failure_count INTEGER NOT NULL DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (tool_id, category)
                    );
                """)
                cur.execute("""
                    ALTER TABLE bayesian_weights 
                    ADD COLUMN IF NOT EXISTS success_count INTEGER NOT NULL DEFAULT 0, 
                    ADD COLUMN IF NOT EXISTS failure_count INTEGER NOT NULL DEFAULT 0;
                """)
                
                # 2. keyword_weights
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS keyword_weights (
                        keyword VARCHAR(255) PRIMARY KEY,
                        weight FLOAT NOT NULL DEFAULT 1.0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # 3. routing_failures
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS routing_failures (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        task TEXT NOT NULL,
                        wrong_path VARCHAR(255) NOT NULL,
                        correct_path VARCHAR(255) NOT NULL
                    );
                """)

                # 4. agent_evaluations
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS agent_evaluations (
                        id SERIAL PRIMARY KEY,
                        agent_id VARCHAR(255) NOT NULL,
                        task_id VARCHAR(255) NOT NULL,
                        run_id VARCHAR(255) NOT NULL,
                        prompt_hash VARCHAR(64) NOT NULL,
                        score FLOAT NOT NULL DEFAULT 0.0,
                        speed_sec FLOAT,
                        token_cost FLOAT,
                        compliance_score FLOAT,
                        eval_feedback TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 5. agent_prompts
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS agent_prompts (
                        prompt_hash VARCHAR(64) PRIMARY KEY,
                        agent_id VARCHAR(255) NOT NULL,
                        system_prompt TEXT NOT NULL,
                        meta_data JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                logger.info("✅ PostgreSQL tables initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize PostgreSQL tables: {e}")
