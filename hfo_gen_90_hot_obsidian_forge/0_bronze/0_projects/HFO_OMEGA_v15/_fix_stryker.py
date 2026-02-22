import json, pathlib

cfg = {
    "$schema": "./node_modules/@stryker-mutator/core/schema/stryker-schema.json",
    "packageManager": "npm",
    "reporters": ["html", "clear-text", "progress"],
    "testRunner": "jest",
    "coverageAnalysis": "all",
    "jest": {"configFile": "./jest.stryker.config.js", "enableFindRelatedTests": True},
    "mutate": ["event_bus.ts", "kalman_filter.ts"],
    "thresholds": {"high": 90, "low": 80, "break": 75},
    "timeoutMS": 10000,
    "timeoutFactor": 1.5,
}

p = pathlib.Path("stryker.config.json")
p.write_text(json.dumps(cfg, indent=2), encoding="ascii")
print("Done.", p.stat().st_size, "bytes")
