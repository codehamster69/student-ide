def max_subarray(nums):
    """Divide and conquer, O(n log n)."""
    def go(lo, hi):
        if lo == hi:
            return nums[lo]
        mid = (lo + hi) // 2
        left_best = right_best = float("-inf")
        s = 0
        for i in range(mid, lo - 1, -1):
            s += nums[i]
            left_best = max(left_best, s)
        s = 0
        for i in range(mid + 1, hi + 1):
            s += nums[i]
            right_best = max(right_best, s)
        return max(go(lo, mid), go(mid + 1, hi), left_best + right_best)
    return go(0, len(nums) - 1)


input()
print(max_subarray([int(x) for x in input().split()]))
