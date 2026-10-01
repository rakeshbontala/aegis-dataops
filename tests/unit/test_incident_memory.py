import json

from engine.prevention import incident_memory


def write_memory(directory, incident_id, signature, verified=True):
    (directory / f"{incident_id}.json").write_text(
        json.dumps(
            {
                "incident_id": incident_id,
                "incident_type": "SCHEMA_DRIFT",
                "pipeline": "customer_gold_pipeline",
                "incident_signature": signature,
                "recovery": {
                    "verification_completed": verified,
                    "selected_strategy": {"strategy_id": "REC-002"},
                },
            }
        ),
        encoding="utf-8",
    )


def test_similar_incidents_require_matching_signature_and_verification(monkeypatch, tmp_path):
    monkeypatch.setattr(incident_memory, "HISTORICAL_DIR", tmp_path)
    signature = {"error_type": "SCHEMA_DRIFT", "unexpected_columns": ["segment"]}
    write_memory(tmp_path, "INC-20990101-001", signature)
    write_memory(tmp_path, "INC-20990101-002", signature)
    write_memory(tmp_path, "INC-20990101-003", {"error_type": "SCHEMA_DRIFT"})
    write_memory(tmp_path, "INC-20990101-004", signature, verified=False)

    matches = incident_memory.find_similar_incidents("INC-20990101-001")

    assert [item["incident_id"] for item in matches] == ["INC-20990101-002"]
    assert matches[0]["selected_strategy"]["strategy_id"] == "REC-002"