---
title: Special methods and inheritance
summary: __repr__, __eq__, __add__, __lt__, and classes built on other classes.
---
Methods with double underscores ("dunder" methods) let your objects work with Python's built-in syntax: printing, `==`, `+`, `<`, `len()` and more.

```python
class Vector:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __repr__(self):                    # how it prints
        return f"Vector({self.x}, {self.y})"

    def __add__(self, other):              # v + w
        return Vector(self.x + other.x, self.y + other.y)

    def __mul__(self, k):                  # v * 3
        return Vector(self.x * k, self.y * k)

    def __eq__(self, other):               # v == w
        return (self.x, self.y) == (other.x, other.y)

    def __abs__(self):                     # abs(v)
        return (self.x ** 2 + self.y ** 2) ** 0.5

v, w = Vector(3, 4), Vector(1, -1)
print(v + w, v * 2, abs(v), v == Vector(3, 4))
```

**Inheritance** builds a new class on an existing one. The child gets every method of the parent and can add or *override* some. `super()` calls the parent's version.

```python
class Shape:
    def __init__(self, name):
        self.name = name
    def area(self):
        return 0
    def __repr__(self):
        return f"{self.name} with area {self.area():.2f}"

class Circle(Shape):
    def __init__(self, r):
        super().__init__("circle")
        self.r = r
    def area(self):
        return 3.14159 * self.r ** 2

class Square(Shape):
    def __init__(self, side):
        super().__init__("square")
        self.side = side
    def area(self):
        return self.side ** 2

for s in [Circle(1), Square(3)]:
    print(s)            # each uses its own area(): polymorphism
```

Things to try:

1. Add `__sub__` and `__neg__` to `Vector`.
2. Add `__len__` to a class and call `len()` on it.
3. Add a `Rectangle` class, and make `Square` inherit from it instead of from `Shape`.

## Exercise

Write a class `Fraction` that keeps a numerator and denominator in lowest terms (use `math.gcd`; the denominator is always positive). It needs `__add__`, `__mul__`, `__lt__` and `__repr__` (printing as `3/4`, or just `2` when the denominator is 1). The program reads fractions, prints their sum, their product and the smallest one.

```input
3
1/2
3/4
-1/6
```

```python starter
from math import gcd


class Fraction:
    def __init__(self, num, den=1):
        self.num, self.den = num, den


fracs = []
for _ in range(int(input())):
    a, b = input().split("/")
    fracs.append(Fraction(int(a), int(b)))
total, product = Fraction(0), Fraction(1)
for f in fracs:
    total = total + f
    product = product * f
print(total)
print(product)
print(min(fracs))
```

```python solution
from math import gcd


class Fraction:
    def __init__(self, num, den=1):
        if den < 0:
            num, den = -num, -den
        g = gcd(num, den) or 1
        self.num, self.den = num // g, den // g

    def __add__(self, other):
        return Fraction(self.num * other.den + other.num * self.den, self.den * other.den)

    def __mul__(self, other):
        return Fraction(self.num * other.num, self.den * other.den)

    def __lt__(self, other):
        return self.num * other.den < other.num * self.den

    def __repr__(self):
        return str(self.num) if self.den == 1 else f"{self.num}/{self.den}"


fracs = []
for _ in range(int(input())):
    a, b = input().split("/")
    fracs.append(Fraction(int(a), int(b)))
total, product = Fraction(0), Fraction(1)
for f in fracs:
    total = total + f
    product = product * f
print(total)
print(product)
print(min(fracs))
```

```tests
{"name": "example", "stdin": "3\n1/2\n3/4\n-1/6\n", "expected": "13/12\n-1/16\n-1/6"}
{"name": "whole result", "stdin": "2\n1/2\n1/2\n", "expected": "1\n1/4\n1/2"}
{"name": "negative denominator", "stdin": "2\n2/-4\n1/3\n", "expected": "-1/6\n-1/6\n-1/2", "hidden": true}
```
