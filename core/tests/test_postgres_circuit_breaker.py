import pytest
from unittest.mock import patch
from tools.memory.postgres_client import get_connection, reset_postgres_circuit

def test_postgres_circuit_breaker_fast_fail():
    reset_postgres_circuit()
    
    with patch("tools.memory.postgres_client.psycopg.connect") as mock_connect:
        mock_connect.side_effect = RuntimeError("Connection refused")
        
        with pytest.raises(RuntimeError) as exc_info:
            get_connection()
        assert "Connection refused" in str(exc_info.value)
        assert mock_connect.call_count == 1
        
        # Second call should fast-fail via circuit breaker without calling psycopg.connect
        with pytest.raises(RuntimeError) as exc_info2:
            get_connection()
        assert "circuit breaker active" in str(exc_info2.value)
        assert mock_connect.call_count == 1  # Not incremented!
        
        # Reset circuit allows a fresh connection attempt
        reset_postgres_circuit()
        with pytest.raises(RuntimeError) as exc_info3:
            get_connection()
        assert "Connection refused" in str(exc_info3.value)
        assert mock_connect.call_count == 2
