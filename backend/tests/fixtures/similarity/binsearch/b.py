def first_position(values, target):
    lo, hi = 0, len(values) - 1
    found = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if values[mid] == target:
            found = mid
            hi = mid - 1
        elif values[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return found


n, q = [int(t) for t in input().split()]
arr = [int(t) for t in input().split()]
for _ in range(q):
    pos = first_position(arr, int(input()))
    print(pos + 1 if pos >= 0 else -1)
