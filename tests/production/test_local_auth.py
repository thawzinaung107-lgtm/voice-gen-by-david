from production.passwords import hash_password, verify_password

def test_password_hash_round_trip_and_mismatch():
    stored = hash_password('correct-horse-battery')
    assert stored.startswith('pbkdf2_sha256$')
    assert verify_password('correct-horse-battery', stored)
    assert not verify_password('wrong-horse-battery', stored)
    assert not verify_password('correct-horse-battery', 'not-a-hash')
