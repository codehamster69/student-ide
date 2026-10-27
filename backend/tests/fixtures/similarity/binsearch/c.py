import sys

it = iter(sys.stdin.read().split())
n = int(next(it))
q = int(next(it))
first_index = {}
for position in range(1, n + 1):
    value = int(next(it))
    first_index.setdefault(value, position)
answers = [str(first_index.get(int(next(it)), -1)) for _ in range(q)]
print("\n".join(answers))
