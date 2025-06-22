import re


def parse_location_tokens(token_str: str) -> int:
    """Extract the y0 coordinate from a token string"""
    numbers = re.findall(r"\d+", token_str)
    if len(numbers) >= 2:
        return int(numbers[1])
    raise ValueError("could not parse location")
