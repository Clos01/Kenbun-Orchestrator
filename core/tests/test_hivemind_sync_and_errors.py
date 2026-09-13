from tools.memory.hivemind_sync import (
    compute_record_checksum,
    inspect_local_hivemind_bin,
)
from tools.utils.error_codes import KenbunErrorCode, format_error


def test_error_codes_taxonomy():
    assert KenbunErrorCode.MODEL_ENDPOINT_UNREACHABLE == "KB-E101"
    assert KenbunErrorCode.MASTER_HIVEMIND_UNREACHABLE == "KB-E401"
    assert KenbunErrorCode.UNVERIFIED_BIN_PURGE_BLOCKED == "KB-E403"
    assert KenbunErrorCode.MODEL_ENDPOINT_UNREACHABLE.category == "Model & Inference"
    assert (
        KenbunErrorCode.MASTER_HIVEMIND_UNREACHABLE.category
        == "Hivemind Synchronization"
    )

    formatted = format_error(KenbunErrorCode.MODEL_TIMEOUT, "Timed out after 30s")
    assert formatted["status"] == "error"
    assert formatted["error_code"] == "KB-E102"
    assert "KB-E102" in formatted["message"]


def test_checksum_computation():
    c1 = compute_record_checksum("id1", "content 1", '{"title": "t1"}')
    c2 = compute_record_checksum("id1", "content 1", '{"title": "t1"}')
    c3 = compute_record_checksum("id1", "content 2", '{"title": "t1"}')
    assert c1 == c2
    assert c1 != c3
    assert len(c1) == 64


def test_inspect_and_defensive_purge():
    inspection = inspect_local_hivemind_bin()
    assert "total_records" in inspection
    assert "synced_records" in inspection
    assert "can_safely_purge" in inspection
    assert isinstance(inspection["can_safely_purge"], bool)
