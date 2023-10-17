from promptflow import tool
from typing import List, Union, Dict


def dummy_list(prefix: str, **kwargs) -> List[Dict[str, Union[str, int, float, list, Dict]]]:
    # dummy random.
    import random

    words = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew", "kiwi", "lemon"]
    result = []
    for i in range(10):
        random_word = random.choice(words)
        cur_item = {
            # for backend use.
            "value": random_word,
            # for UI display.
            "display_value": f"{prefix}_{random_word}",
            "hyperlink": f'https://www.google.com/search?q={random_word}',
            # information icon tip.
            "description": f"this is {i} item",
        }
        result.append(cur_item)
    return result


@tool
def my_tool(input_text: list, input_prefix: str) -> str:
    # Replace with your tool code.
    # Usually connection contains configs to connect to an API.
    # Use CustomConnection is a dict. You can use it like: connection.api_key, connection.api_base
    # Not all tools need a connection. You can remove it if you don't need it.
    return "Hello " + ','.join(input_text) + " " + input_prefix
