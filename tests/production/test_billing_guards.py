import uuid
import pytest
from fastapi import HTTPException
from production.service import approve

class Row(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

class FakeDB:
    def __init__(self, row):
        self.row = row
        self.writes = []
    def execute(self, statement, params=None):
        self.writes.append((str(statement), params or {}))
        return self

def test_screenshot_without_clean_scan_cannot_credit():
    db = FakeDB({'user_id': uuid.uuid4(), 'state': 'pending', 'evidence_key': 'evidence/shot', 'evidence_state': 'pending_scan', 'verification_reference': None})
    with pytest.raises(HTTPException) as error:
        approve(db, uuid.uuid4(), uuid.uuid4(), 'bank-verified-independent')
    assert error.value.status_code == 409
    assert db.writes == []

def test_rejected_evidence_cannot_credit():
    db = FakeDB({'user_id': uuid.uuid4(), 'state': 'pending', 'evidence_key': 'evidence/shot', 'evidence_state': 'rejected', 'verification_reference': None})
    with pytest.raises(HTTPException) as error:
        approve(db, uuid.uuid4(), uuid.uuid4(), 'bank-verified-independent')
    assert error.value.status_code == 409

def test_repeated_approval_does_not_write_again():
    reference = 'bank-verified-independent'
    db = FakeDB({'user_id': uuid.uuid4(), 'state': 'approved', 'evidence_key': 'evidence/shot', 'evidence_state': 'clean', 'verification_reference': reference})
    assert approve(db, uuid.uuid4(), uuid.uuid4(), reference)['state'] == 'approved'
    assert db.writes == []
