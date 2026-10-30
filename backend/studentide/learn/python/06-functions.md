---
title: Functions
summary: def, parameters, return values and default arguments.
---
`def` gives a block of code a name. Parameters are its inputs, and `return` sends a result back.

```python
def area(width, height=1):
    return width * height

def describe(n):
    kind = "even" if n % 2 == 0 else "odd"
    return f"{n} is {kind}"

print(area(4, 5))
print(area(4))          # height falls back to its default
print(describe(7))
```

A function without `return` gives back `None`. Variables made inside a function exist only while it runs.

Things to try:

1. Call `area(height=3, width=2)`. Arguments can be given by name in any order.
2. Remove the `return` from `area` and print its result.
3. Write `def average(xs)` and use it on a list.

## Exercise

Write `count_vowels(word)` that returns how many of the letters a, e, i, o, u (lower or upper case) are in `word`. The last line already prints the answer for the word in the Input box.

```input
Programming
```

```python starter
def count_vowels(word):
    return 0

print(count_vowels(input().strip()))
```

```python solution
def count_vowels(word):
    return sum(1 for ch in word.lower() if ch in "aeiou")

print(count_vowels(input().strip()))
```

```tests
{"name": "Programming", "stdin": "Programming\n", "expected": "3"}
{"name": "no vowels", "stdin": "rhythm\n", "expected": "0"}
{"name": "upper case", "stdin": "AEIOU\n", "expected": "5"}
```
