def get_path(data: dict, path: str):
    """get_path({"a": {"b": 1}}, "a.b") -> 1"""
    for part in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


def set_path(data: dict, path: str, value):
    parts = path.split(".")
    for part in parts[:-1]:
        data = data.setdefault(part, {})
    data[parts[-1]] = value
