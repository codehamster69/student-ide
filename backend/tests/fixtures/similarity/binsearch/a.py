import bisect

n, q = map(int, input().split())
a = list(map(int, input().split()))
for _ in range(q):
    x = int(input())
    i = bisect.bisect_left(a, x)
    print(i + 1 if i < n and a[i] == x else -1)
