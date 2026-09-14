import re


def natural_sort_key(path: str) -> tuple:
    """Sort folder components and ASCII digit runs naturally with stable ties."""
    components = tuple(
        tuple(
            (1, int(part)) if part.isascii() and part.isdigit() else (0, part.casefold())
            for part in re.split(r"([0-9]+)", component)
        )
        for component in path.replace("\\", "/").split("/")
    )
    return components, path.casefold(), path
