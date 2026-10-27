import sys


def solve(values):
    prefix = 0
    smallest = 0
    answer = None
    for v in values:
        prefix += v
        if answer is None or prefix - smallest > answer:
            answer = prefix - smallest
        smallest = min(smallest, prefix)
    return answer


tokens = sys.stdin.read().split()
count = int(tokens[0])
print(solve([int(t) for t in tokens[1 : count + 1]]))
