"""Contract tests for the agent tool surface.

Every schema sent to the model must have a matching executor and vice versa — a
mismatch means the model can request a tool that doesn't exist, or an executor
is unreachable. These checks don't hit the network or the DB.
"""
from app.agent.tools import EXECUTORS, TOOLS


def test_every_tool_has_an_executor_and_vice_versa():
    tool_names = {t["name"] for t in TOOLS}
    assert tool_names == set(EXECUTORS), "TOOLS and EXECUTORS names must match exactly"


def test_tool_schemas_are_well_formed():
    for tool in TOOLS:
        assert tool["name"], "tool missing a name"
        assert tool.get("description"), f"{tool['name']} missing a description"
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert isinstance(schema.get("properties", {}), dict)


def test_required_fields_are_declared_properties():
    for tool in TOOLS:
        schema = tool["input_schema"]
        properties = set(schema.get("properties", {}))
        for required in schema.get("required", []):
            assert required in properties, (
                f"{tool['name']} requires {required!r} but it isn't a declared property"
            )


def test_executors_are_callable():
    for name, fn in EXECUTORS.items():
        assert callable(fn), f"executor {name} is not callable"
