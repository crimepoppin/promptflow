import textwrap
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from promptflow import tool
from promptflow._core._errors import NotSupported, PackageToolNotFoundError
from promptflow._core.tools_manager import (
    NodeSourcePathEmpty,
    ToolLoader,
    collect_package_tools,
    collect_package_tools_and_connections,
    gen_tool_by_source,
    gen_dynamic_list,
)
from promptflow.contracts.flow import Node, ToolSource, ToolSourceType
from promptflow.contracts.tool import Tool, ToolType
from promptflow.exceptions import UserErrorException


@pytest.mark.unittest
class TestToolLoader:
    def test_load_tool_for_node_with_invalid_node(self):
        tool_loader = ToolLoader(working_dir="test_working_dir")
        node: Node = Node(name="test", tool="test_tool", inputs={}, type=ToolType.PYTHON)
        with pytest.raises(UserErrorException, match="Node test does not have source defined."):
            tool_loader.load_tool_for_node(node)

        node: Node = Node(
            name="test", tool="test_tool", inputs={}, type=ToolType.PYTHON, source=ToolSource(type="invalid_type")
        )
        with pytest.raises(
            NotImplementedError, match="Tool source type invalid_type for python tool is not supported yet."
        ):
            tool_loader.load_tool_for_node(node)

        node: Node = Node(
            name="test", tool="test_tool", inputs={}, type=ToolType.CUSTOM_LLM, source=ToolSource(type="invalid_type")
        )
        with pytest.raises(
            NotImplementedError, match="Tool source type invalid_type for custom_llm tool is not supported yet."
        ):
            tool_loader.load_tool_for_node(node)

        node: Node = Node(
            name="test", tool="test_tool", inputs={}, type="invalid_type", source=ToolSource(type=ToolSourceType.Code)
        )
        with pytest.raises(NotImplementedError, match="Tool type invalid_type is not supported yet."):
            tool_loader.load_tool_for_node(node)

    def test_load_tool_for_package_node(self, mocker):
        package_tools = {"test_tool": Tool(name="test_tool", type=ToolType.PYTHON, inputs={}).serialize()}
        mocker.patch("promptflow._core.tools_manager.collect_package_tools", return_value=package_tools)
        tool_loader = ToolLoader(
            working_dir="test_working_dir", package_tool_keys=["promptflow._core.tools_manager.collect_package_tools"]
        )
        node: Node = Node(
            name="test",
            tool="test_tool",
            inputs={},
            type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Package, tool="test_tool"),
        )
        tool = tool_loader.load_tool_for_node(node)
        assert tool.name == "test_tool"

        node: Node = Node(
            name="test",
            tool="test_tool",
            inputs={},
            type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Package, tool="invalid_tool"),
        )
        msg = (
            "Package tool 'invalid_tool' is not found in the current environment. "
            "All available package tools are: ['test_tool']."
        )
        with pytest.raises(PackageToolNotFoundError) as ex:
            tool_loader.load_tool_for_node(node)
            assert str(ex.value) == msg

    def test_load_tool_for_script_node(self):
        working_dir = Path(__file__).parent
        tool_loader = ToolLoader(working_dir=working_dir)
        file = "test_tools_manager.py"
        node: Node = Node(
            name="test",
            tool="sample_tool",
            inputs={},
            type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Code, path=file),
        )
        tool = tool_loader.load_tool_for_node(node)
        assert tool.name == "sample_tool"


# This tool is for testing tools_manager.ToolLoader.load_tool_for_script_node
@tool
def sample_tool(input: str):
    return input


@pytest.mark.unittest
class TestToolsManager:
    @pytest.mark.parametrize(
        "tool_source, tool_type, error_code, error_message",
        [
            (
                ToolSource(type=ToolSourceType.Package, tool="fake_name", path="fake_path"),
                None,
                PackageToolNotFoundError,
                "Package tool 'fake_name' is not found in the current environment. "
                f"Available package tools include: '{','.join(collect_package_tools().keys())}'. "
                "Please ensure that the required tool package is installed in current environment.",
            ),
            (
                ToolSource(tool="fake_name", path=None),
                ToolType.PYTHON,
                NodeSourcePathEmpty,
                "Invalid node definitions found in the flow graph. The node 'fake_name' is missing its source path. "
                "Please kindly add the source path for the node 'fake_name' in the YAML file "
                "and try the operation again.",
            ),
            (
                ToolSource(tool="fake_name", path=Path("test_tools_manager.py")),
                ToolType.CUSTOM_LLM,
                NotSupported,
                "The tool type custom_llm is currently not supported for generating tools using source code. "
                "Please choose from the available types: python,prompt,llm. "
                "If you need further assistance, kindly contact support.",
            ),
        ],
    )
    def test_gen_tool_by_source_error(self, tool_source, tool_type, error_code, error_message):
        working_dir = Path(__file__).parent
        with pytest.raises(error_code) as ex:
            gen_tool_by_source("fake_name", tool_source, tool_type, working_dir),
        assert str(ex.value) == error_message

    def test(self):
        tools, specs, templates = collect_package_tools_and_connections()
        from promptflow._sdk._utils import refresh_connections_dir

        refresh_connections_dir(specs, templates)

    def test_collect_package_tools_and_connections(self, install_custom_tool_pkg):
        # Need to reload pkg_resources to get the latest installed tools
        import importlib

        import pkg_resources

        importlib.reload(pkg_resources)

        yaml = YAML()
        yaml.preserve_quotes = True
        keys = ["my_tool_package.tools.my_tool_2.MyTool.my_tool"]
        tools, specs, templates = collect_package_tools_and_connections(keys)
        assert len(tools) == 1
        assert specs == {
            "my_tool_package.connections.MyFirstConnection": {
                "connectionCategory": "CustomKeys",
                "flowValueType": "CustomConnection",
                "connectionType": "MyFirstConnection",
                "ConnectionTypeDisplayName": "MyFirstConnection",
                "configSpecs": [
                    {"name": "api_key", "displayName": "Api Key", "configValueType": "Secret", "isOptional": False},
                    {"name": "api_base", "displayName": "Api Base", "configValueType": "str", "isOptional": True},
                ],
                "module": "my_tool_package.connections",
                "package": "test-custom-tools",
                "package_version": "0.0.2",
            }
        }

        expected_template = {
            "name": "to_replace_with_connection_name",
            "type": "custom",
            "custom_type": "MyFirstConnection",
            "module": "my_tool_package.connections",
            "package": "test-custom-tools",
            "package_version": "0.0.2",
            "configs": {"api_base": "This is my first connection."},
            "secrets": {"api_key": "to_replace_with_api_key"},
        }
        loaded_yaml = yaml.load(templates["my_tool_package.connections.MyFirstConnection"])
        assert loaded_yaml == expected_template

        keys = ["my_tool_package.tools.my_tool_with_custom_strong_type_connection.my_tool"]
        tools, specs, templates = collect_package_tools_and_connections(keys)
        assert len(templates) == 1
        expected_template = """
            name: "to_replace_with_connection_name"
            type: custom
            custom_type: MyCustomConnection
            module: my_tool_package.tools.my_tool_with_custom_strong_type_connection
            package: test-custom-tools
            package_version: 0.0.2
            configs:
              api_url: "This is a fake api url."  # String, The api url.
            secrets:      # must-have
              api_key: "to_replace_with_api_key"  # String, The api key.
            """

        content = templates["my_tool_package.tools.my_tool_with_custom_strong_type_connection.MyCustomConnection"]
        expected_template_str = textwrap.dedent(expected_template)

        assert content in expected_template_str

    def test_dynamic_list(self):
        func_path="my_tool_package.tools.tool_with_dynamic_list_input.dummy_list"
        func_kwargs={"prefix": "My"}
        result = gen_dynamic_list(func_path, func_kwargs)
        assert len(result) == 10
        from promptflow._sdk._utils import _gen_dynamic_list

        _result = _gen_dynamic_list({
            "func_path": func_path, "func_kwargs": func_kwargs})
        print(_result)
