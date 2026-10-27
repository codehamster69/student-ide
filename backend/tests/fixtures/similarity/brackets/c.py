import sys

OPEN = "([{"
CLOSE = ")]}"


def check(line):
    depth_stack = []
    for ch in line:
        if ch in OPEN:
            depth_stack.append(OPEN.index(ch))
            continue
        kind = CLOSE.index(ch)
        if len(depth_stack) == 0:
            return False
        if depth_stack[-1] != kind:
            return False
        depth_stack.pop()
    return len(depth_stack) == 0


line = sys.stdin.readline().rstrip("\n")
sys.stdout.write("YES\n" if check(line) else "NO\n")
