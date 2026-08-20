import pytest
from repositories.cache_audit_repository import CacheAuditRepository

def test_cache_audit_flow():
    repo = CacheAuditRepository()
    
    # 1. Register a guide
    guide_key = "romanos_12_principiante"
    audit = repo.register_guide(guide_key, "/path/to/guide.md")
    
    assert audit.id is not None
    assert audit.guide_key == guide_key
    assert audit.is_stale is False
    
    # 2. Check freshness
    assert repo.is_guide_fresh(guide_key) is True
    assert repo.is_guide_fresh("non_existent_key") is False
    
    # 3. Invalidate ALL (simulating new knowledge ingested)
    affected = repo.invalidate_all()
    assert affected >= 1
    
    # 4. Verify it's stale now
    assert repo.is_guide_fresh(guide_key) is False
    
    # 5. Check stale list
    stale_guides = repo.get_stale_guides()
    assert any(g.guide_key == guide_key for g in stale_guides)
