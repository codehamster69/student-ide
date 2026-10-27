import sys

data = sys.stdin.read().split()
N = int(data[0])
flags = bytearray([1]) * (N + 1)
flags[0:2] = b"\x00\x00"[: min(2, N + 1)]
p = 2
while p * p <= N:
    if flags[p]:
        flags[p * p :: p] = bytearray(len(range(p * p, N + 1, p)))
    p += 1
total = 0
for value in flags:
    total += value
sys.stdout.write(str(total) + "\n")
