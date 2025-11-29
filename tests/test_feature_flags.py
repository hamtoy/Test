"""Tests for Feature Flags."""

import json
from pathlib import Path

import pytest

from src.infra.feature_flags import FeatureFlags


@pytest.fixture
def temp_flags_file(tmp_path):
    """Create a temporary feature flags config file."""
    flags_file = tmp_path / "config" / "feature_flags.json"
    flags_file.parent.mkdir(parents=True, exist_ok=True)

    flags_config = {
        "test_feature": {
            "enabled": True,
            "description": "Test feature",
            "rollout_percent": 100,
            "environments": ["development", "staging", "production"],
            "whitelist": [],
        },
        "limited_rollout": {
            "enabled": True,
            "description": "Limited rollout feature",
            "rollout_percent": 50,
            "environments": ["development"],
            "whitelist": [],
        },
        "whitelist_only": {
            "enabled": True,
            "description": "Whitelist only feature",
            "rollout_percent": 100,
            "environments": ["development"],
            "whitelist": ["user1", "user2"],
        },
        "disabled_feature": {
            "enabled": False,
            "description": "Disabled feature",
            "rollout_percent": 100,
            "environments": ["development"],
        },
        "ab_test_feature": {
            "enabled": True,
            "description": "A/B test feature",
            "rollout_percent": 100,
            "environments": ["development"],
            "variants": ["control", "variant_a", "variant_b"],
        },
        "context_rules_feature": {
            "enabled": True,
            "description": "Feature with context rules",
            "rollout_percent": 100,
            "environments": ["development"],
            "rules": [{"field": "user_tier", "operator": "equals", "value": "premium"}],
        },
    }

    flags_file.write_text(json.dumps(flags_config, indent=2), encoding="utf-8")
    return flags_file


@pytest.fixture
def empty_flags_file(tmp_path):
    """Create an empty flags file."""
    flags_file = tmp_path / "config" / "feature_flags.json"
    flags_file.parent.mkdir(parents=True, exist_ok=True)
    flags_file.write_text("{}", encoding="utf-8")
    return flags_file


def test_feature_flags_init():
    """Test feature flags initialization with default path."""
    flags = FeatureFlags()
    assert flags.config_file == Path("config/feature_flags.json")


def test_feature_flags_init_custom_path(temp_flags_file):
    """Test feature flags initialization with custom path."""
    flags = FeatureFlags(config_file=temp_flags_file)
    assert flags.config_file == temp_flags_file


def test_load_flags(temp_flags_file):
    """Test loading flags from file."""
    flags = FeatureFlags(config_file=temp_flags_file)
    assert "test_feature" in flags.flags
    assert flags.flags["test_feature"]["enabled"] is True


def test_load_flags_missing_file(tmp_path):
    """Test loading from non-existent file."""
    missing_file = tmp_path / "missing.json"
    flags = FeatureFlags(config_file=missing_file)
    assert flags.flags == {}


def test_is_enabled_basic(temp_flags_file, monkeypatch):
    """Test basic feature enabled check."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    flags = FeatureFlags(config_file=temp_flags_file)
    assert flags.is_enabled("test_feature") is True
    assert flags.is_enabled("disabled_feature") is False


def test_is_enabled_unknown_flag(temp_flags_file, monkeypatch):
    """Test checking unknown flag."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    flags = FeatureFlags(config_file=temp_flags_file)
    assert flags.is_enabled("unknown_flag") is False


def test_is_enabled_environment_restriction(temp_flags_file, monkeypatch):
    """Test environment restriction."""
    flags = FeatureFlags(config_file=temp_flags_file)

    # limited_rollout only enabled in development environment
    # First test with 100% rollout feature to verify environment check works
    monkeypatch.setenv("ENVIRONMENT", "development")
    # test_feature is available in all environments
    assert flags.is_enabled("test_feature") is True

    # limited_rollout only in development - check environment restriction
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Should be False because production is not in the environments list
    assert flags.is_enabled("limited_rollout", user_id="test_user") is False


def test_is_enabled_whitelist(temp_flags_file, monkeypatch):
    """Test whitelist functionality."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    flags = FeatureFlags(config_file=temp_flags_file)

    # User in whitelist
    assert flags.is_enabled("whitelist_only", user_id="user1") is True

    # User not in whitelist
    assert flags.is_enabled("whitelist_only", user_id="user3") is False


def test_is_enabled_rollout_percent(temp_flags_file, monkeypatch):
    """Test rollout percentage."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    flags = FeatureFlags(config_file=temp_flags_file)

    # With 50% rollout, some users should be enabled, some not
    # Using deterministic hash, the result should be consistent
    result1 = flags.is_enabled("limited_rollout", user_id="user_a")
    result2 = flags.is_enabled("limited_rollout", user_id="user_a")
    assert result1 == result2  # Same user should get same result


def test_is_enabled_no_user_id_with_rollout(temp_flags_file, monkeypatch):
    """Test rollout without user_id."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    flags = FeatureFlags(config_file=temp_flags_file)

    # Without user_id, should return False for partial rollout
    assert flags.is_enabled("limited_rollout") is False


def test_is_enabled_context_rules(temp_flags_file, monkeypatch):
    """Test context-based rules."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    flags = FeatureFlags(config_file=temp_flags_file)

    # User tier matches
    assert (
        flags.is_enabled(
            "context_rules_feature",
            context={"user_tier": "premium"},
        )
        is True
    )

    # User tier doesn't match
    assert (
        flags.is_enabled(
            "context_rules_feature",
            context={"user_tier": "basic"},
        )
        is False
    )


def test_check_rules_equals(temp_flags_file):
    """Test equals rule operator."""
    flags = FeatureFlags(config_file=temp_flags_file)
    rules = [{"field": "tier", "operator": "equals", "value": "premium"}]

    assert flags._check_rules(rules, {"tier": "premium"}) is True
    assert flags._check_rules(rules, {"tier": "basic"}) is False


def test_check_rules_not_equals(temp_flags_file):
    """Test not_equals rule operator."""
    flags = FeatureFlags(config_file=temp_flags_file)
    rules = [{"field": "tier", "operator": "not_equals", "value": "premium"}]

    assert flags._check_rules(rules, {"tier": "basic"}) is True
    assert flags._check_rules(rules, {"tier": "premium"}) is False


def test_check_rules_greater_than(temp_flags_file):
    """Test greater_than rule operator."""
    flags = FeatureFlags(config_file=temp_flags_file)
    rules = [{"field": "score", "operator": "greater_than", "value": 50}]

    assert flags._check_rules(rules, {"score": 75}) is True
    assert flags._check_rules(rules, {"score": 25}) is False


def test_check_rules_less_than(temp_flags_file):
    """Test less_than rule operator."""
    flags = FeatureFlags(config_file=temp_flags_file)
    rules = [{"field": "score", "operator": "less_than", "value": 50}]

    assert flags._check_rules(rules, {"score": 25}) is True
    assert flags._check_rules(rules, {"score": 75}) is False


def test_check_rules_contains(temp_flags_file):
    """Test contains rule operator."""
    flags = FeatureFlags(config_file=temp_flags_file)
    rules = [{"field": "tags", "operator": "contains", "value": "vip"}]

    assert flags._check_rules(rules, {"tags": "vip,premium"}) is True
    assert flags._check_rules(rules, {"tags": "basic"}) is False


def test_check_rules_in(temp_flags_file):
    """Test in rule operator."""
    flags = FeatureFlags(config_file=temp_flags_file)
    rules = [{"field": "region", "operator": "in", "value": ["us", "eu", "asia"]}]

    assert flags._check_rules(rules, {"region": "us"}) is True
    assert flags._check_rules(rules, {"region": "africa"}) is False


def test_get_variant(temp_flags_file, monkeypatch):
    """Test A/B variant selection."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    flags = FeatureFlags(config_file=temp_flags_file)

    # Same user should always get same variant
    variant1 = flags.get_variant("ab_test_feature", "user1")
    variant2 = flags.get_variant("ab_test_feature", "user1")
    assert variant1 == variant2
    assert variant1 in ["control", "variant_a", "variant_b"]


def test_get_variant_no_variants(temp_flags_file):
    """Test variant selection with no variants defined."""
    flags = FeatureFlags(config_file=temp_flags_file)
    variant = flags.get_variant("test_feature", "user1")
    assert variant == "control"


def test_get_variant_unknown_flag(temp_flags_file):
    """Test variant selection for unknown flag."""
    flags = FeatureFlags(config_file=temp_flags_file)
    variant = flags.get_variant("unknown_flag", "user1")
    assert variant == "control"


def test_enable_flag(temp_flags_file, monkeypatch):
    """Test enabling a flag."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    flags = FeatureFlags(config_file=temp_flags_file)

    assert flags.enable_flag("disabled_feature") is True
    assert flags.flags["disabled_feature"]["enabled"] is True


def test_enable_flag_unknown(temp_flags_file):
    """Test enabling an unknown flag."""
    flags = FeatureFlags(config_file=temp_flags_file)
    assert flags.enable_flag("unknown_flag") is False


def test_disable_flag(temp_flags_file, monkeypatch):
    """Test disabling a flag."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    flags = FeatureFlags(config_file=temp_flags_file)

    assert flags.disable_flag("test_feature") is True
    assert flags.flags["test_feature"]["enabled"] is False


def test_disable_flag_unknown(temp_flags_file):
    """Test disabling an unknown flag."""
    flags = FeatureFlags(config_file=temp_flags_file)
    assert flags.disable_flag("unknown_flag") is False


def test_set_rollout_percent(temp_flags_file):
    """Test setting rollout percentage."""
    flags = FeatureFlags(config_file=temp_flags_file)

    assert flags.set_rollout_percent("test_feature", 75) is True
    assert flags.flags["test_feature"]["rollout_percent"] == 75


def test_set_rollout_percent_invalid_range(temp_flags_file):
    """Test setting invalid rollout percentage."""
    flags = FeatureFlags(config_file=temp_flags_file)

    assert flags.set_rollout_percent("test_feature", -10) is False
    assert flags.set_rollout_percent("test_feature", 150) is False


def test_set_rollout_percent_unknown_flag(temp_flags_file):
    """Test setting rollout for unknown flag."""
    flags = FeatureFlags(config_file=temp_flags_file)
    assert flags.set_rollout_percent("unknown_flag", 50) is False


def test_list_flags(temp_flags_file):
    """Test listing all flags."""
    flags = FeatureFlags(config_file=temp_flags_file)
    flag_list = flags.list_flags()

    assert isinstance(flag_list, list)
    assert len(flag_list) > 0

    for flag_info in flag_list:
        assert "name" in flag_info
        assert "enabled" in flag_info
        assert "description" in flag_info
        assert "rollout_percent" in flag_info


def test_save_flags(temp_flags_file):
    """Test saving flags to file."""
    flags = FeatureFlags(config_file=temp_flags_file)
    flags.flags["test_feature"]["rollout_percent"] = 25

    assert flags.save_flags() is True

    # Reload and verify
    flags2 = FeatureFlags(config_file=temp_flags_file)
    assert flags2.flags["test_feature"]["rollout_percent"] == 25
