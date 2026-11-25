"""The thesis event-schema table is generated from schema.py and must stay in step with it."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_schema_appendix.py"


def test_thesis_schema_table_is_up_to_date():
    spec = importlib.util.spec_from_file_location("build_schema_appendix", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.OUT.read_text() == mod.build(), "rerun backend/scripts/build_schema_appendix.py"
