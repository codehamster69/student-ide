"""Small Python programs the synthetic typists "write".

Lab-style solutions of the kind first-year students produce, with the
occasional comment line, because comment keystrokes are handled apart from
code keystrokes (Nosi found comments look like retyping). Programs are
written one after another until the simulated session ends.
"""

PROGRAMS: list[str] = [
    '''\
n = int(input())
# print fizz buzz for each number
for i in range(1, n + 1):
    if i % 15 == 0:
        print("FizzBuzz")
    elif i % 3 == 0:
        print("Fizz")
    elif i % 5 == 0:
        print("Buzz")
    else:
        print(i)
''',
    '''\
line = input()
counts = {}
# strip punctuation and count each word
for word in line.lower().split():
    word = word.strip(".,!?;:")
    if word:
        counts[word] = counts.get(word, 0) + 1
order = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
for word, c in order:
    print(word, c)
''',
    '''\
def is_prime(n):
    # trial division up to the square root
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


limit = int(input())
primes = [p for p in range(limit) if is_prime(p)]
print(len(primes), primes[-5:])
''',
    '''\
def binary_search(items, target):
    lo, hi = 0, len(items) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if items[mid] == target:
            return mid
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


data = sorted(int(x) for x in input().split())
# look up a few values
for q in [3, 7, 42]:
    print(q, binary_search(data, q))
''',
    '''\
class Stack:
    def __init__(self):
        self.items = []

    def push(self, x):
        self.items.append(x)

    def pop(self):
        return self.items.pop()

    def empty(self):
        return not self.items


def balanced(text):
    # every closing bracket must match the last opening one
    pairs = {")": "(", "]": "[", "}": "{"}
    s = Stack()
    for ch in text:
        if ch in "([{":
            s.push(ch)
        elif ch in pairs:
            if s.empty() or s.pop() != pairs[ch]:
                return False
    return s.empty()


print(balanced(input()))
''',
    '''\
def matrix_multiply(a, b):
    rows, cols, inner = len(a), len(b[0]), len(b)
    out = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            total = 0
            for k in range(inner):
                total += a[i][k] * b[k][j]
            out[i][j] = total
    return out


a = [[1, 2], [3, 4]]
b = [[5, 6], [7, 8]]
# expected [[19, 22], [43, 50]]
print(matrix_multiply(a, b))
''',
    '''\
def fib_memo(n, memo=None):
    if memo is None:
        memo = {}
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fib_memo(n - 1, memo) + fib_memo(n - 2, memo)
    return memo[n]


# compare with a simple loop
def fib_loop(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


for n in range(10):
    assert fib_memo(n) == fib_loop(n)
print(fib_memo(80))
''',
    '''\
students = []
count = int(input())
for _ in range(count):
    name, marks = input().split(",")
    students.append((name.strip(), float(marks)))
# average and the toppers
average = sum(m for _, m in students) / len(students)
best = max(m for _, m in students)
toppers = [n for n, m in students if m == best]
print("average:", round(average, 2))
print("toppers:", ", ".join(sorted(toppers)))
below = [n for n, m in students if m < average]
print(len(below), "below average")
''',
    '''\
def bubble_sort(values):
    values = list(values)
    n = len(values)
    for i in range(n):
        swapped = False
        for j in range(n - 1 - i):
            if values[j] > values[j + 1]:
                values[j], values[j + 1] = values[j + 1], values[j]
                swapped = True
        # already sorted, stop early
        if not swapped:
            break
    return values


nums = [int(x) for x in input().split()]
print(bubble_sort(nums))
''',
    '''\
def read_grid():
    rows = int(input())
    return [input().strip() for _ in range(rows)]


def count_islands(grid):
    seen = set()
    islands = 0
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == "#" and (r, c) not in seen:
                islands += 1
                stack = [(r, c)]
                # flood fill this island
                while stack:
                    y, x = stack.pop()
                    if (y, x) in seen:
                        continue
                    seen.add((y, x))
                    for dy, dx in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]):
                            if grid[ny][nx] == "#":
                                stack.append((ny, nx))
    return islands


print(count_islands(read_grid()))
''',
]
