---
title: Modules and import
summary: Use code from the standard library with import, from and as, and the if __name__ == "__main__" line.
---
A **module** is a file of Python code you can reuse. Python ships with a big standard library of them. `import math` gives you the module as a name, and you reach inside with a dot.

```python
import math
import random
from collections import Counter
from statistics import mean as average

print(math.sqrt(16), math.pi, math.gcd(12, 18), math.floor(2.7), math.ceil(2.1))
random.seed(1)                     # same "random" numbers every run
print(random.randint(1, 6), random.choice(["red", "green", "blue"]))
print(Counter("banana").most_common(1))
print(average([2, 4, 9]))
```

- `import math` keeps names inside `math.` so they never clash with yours.
- `from math import sqrt` brings one name in directly.
- `import numpy as np` / `from statistics import mean as average` gives a shorter or clearer name.
- `from math import *` brings in everything. Avoid it: you can no longer tell where a name came from.

Some useful standard modules: `math`, `random`, `statistics`, `collections`, `itertools`, `datetime`, `json`, `re` (text patterns), `os` and `pathlib` (files and folders), `sys`.

Your own file is a module too: another file can `import` it. When a file is imported, all its top-level code runs. To have code that runs only when the file is run directly (not when imported), put it under this line:

```python
def double(x):
    return 2 * x

if __name__ == "__main__":
    # runs for `python main.py`, but not for `import main`
    print(double(21))
```

Things to try:

1. Remove `random.seed(1)` and run a few times.
2. Use `help(math.gcd)` or `dir(math)` to explore a module.
3. Name a variable `math = 5` after the import and call `math.sqrt(4)`. What happens?

## Exercise

Read two positive whole numbers on one line. Using the `math` module, print their greatest common divisor, their least common multiple, and the length of the hypotenuse of a right triangle with those two sides, rounded to 2 decimals, each on its own line.

```input
6 8
```

```python starter
a, b = map(int, input().split())
```

```python solution
import math

a, b = map(int, input().split())
print(math.gcd(a, b))
print(a * b // math.gcd(a, b))
print(f"{math.hypot(a, b):.2f}")
```

```tests
{"name": "6 8", "stdin": "6 8\n", "expected": "2\n24\n10.00"}
{"name": "5 7", "stdin": "5 7\n", "expected": "1\n35\n8.60"}
{"name": "equal", "stdin": "9 9\n", "expected": "9\n9\n12.73", "hidden": true}
```
