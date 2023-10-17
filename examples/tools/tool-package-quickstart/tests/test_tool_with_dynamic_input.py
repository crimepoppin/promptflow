from my_tool_package.tools.tool_with_dynamic_list_input import my_tool, dummy_list


def test_my_tool():
    result = my_tool(input_text=["apple", "banana"], input_prefix="My")
    assert result == 'Hello apple,banana My'


def test_dummy_list():
    result = dummy_list(prefix="My")
    assert len(result) == 10
    assert "value" in result[0]
