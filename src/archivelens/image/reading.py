def spread_indices(index: int, count: int, double: bool, cover: bool) -> tuple[int, ...]:
    if count <= 0:
        return ()
    index = max(0, min(index, count - 1))
    if not double or (cover and index == 0):
        return (index,)
    start = ((index - 1) // 2) * 2 + 1 if cover else (index // 2) * 2
    return tuple(range(start, min(start + 2, count)))
