"""Quick test for deprecation warnings."""

import sys
import warnings

# Test 1: logging_setup
sys.modules.pop("src.logging_setup", None)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    import src.logging_setup

    print(f"Test 1 (logging_setup): {len(w)} warnings")
    if w:
        print(f"  Message: {w[0].message}")
        print(f"  Category: {w[0].category}")

# Test 2: neo4j_utils
sys.modules.pop("src.neo4j_utils", None)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    import src.neo4j_utils

    print(f"Test 2 (neo4j_utils): {len(w)} warnings")
    if w:
        print(f"  Message: {w[0].message}")

# Test 3: worker
sys.modules.pop("src.worker", None)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    import src.worker

    print(f"Test 3 (worker): {len(w)} warnings")
    if w:
        print(f"  Message: {w[0].message}")

# Test 4: data_loader
sys.modules.pop("src.data_loader", None)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    import src.data_loader

    print(f"Test 4 (data_loader): {len(w)} warnings")
    if w:
        print(f"  Message: {w[0].message}")

# Test 5: caching_layer
sys.modules.pop("src.caching_layer", None)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    import src.caching_layer

    print(f"Test 5 (caching_layer): {len(w)} warnings")
    if w:
        for i, warning in enumerate(w):
            print(f"  Warning {i}: {warning.message}")

# Test 6: graph_enhanced_router
sys.modules.pop("src.graph_enhanced_router", None)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    import src.graph_enhanced_router

    print(f"Test 6 (graph_enhanced_router): {len(w)} warnings")
    if w:
        print(f"  Message: {w[0].message}")
