"""Verify that config loading is cached via get_settings()."""

from src.config import get_settings


def main() -> None:
    """Main verification function."""
    # Call get_settings twice
    config1 = get_settings()
    config2 = get_settings()

    # Check that they are the same object (identity check)
    if config1 is config2:
        print("✅ Config caching works! Both calls returned the same object.")
    else:
        print("❌ Config caching failed! Different objects were returned.")
        raise AssertionError("Config caching failed")

    # Show cache info
    cache_info = get_settings.cache_info()
    print(f"   Cache info: {cache_info}")
    print(f"   Hits: {cache_info.hits}, Misses: {cache_info.misses}")


if __name__ == "__main__":
    main()
