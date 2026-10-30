---
title: Classes and objects
summary: Bundle data and the functions that work on it.
---
A **class** is a blueprint; each **object** made from it has its own data (*attributes*) and shares the class's functions (*methods*).

```python
class BankAccount:
    def __init__(self, owner, balance=0):    # runs when an object is made
        self.owner = owner
        self.balance = balance

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("deposit must be positive")
        self.balance += amount

    def withdraw(self, amount):
        if amount > self.balance:
            return False
        self.balance -= amount
        return True

a = BankAccount("asha")
b = BankAccount("ravi", 500)
a.deposit(200)
print(a.withdraw(50), b.withdraw(900))
print(a.owner, a.balance, b.balance)
```

- `self` is the object the method was called on: `a.deposit(200)` runs `deposit` with `self = a`.
- `__init__` sets up the attributes. Each object has its own copy.
- An attribute set on the *class* (outside any method) is shared by all objects; use that for constants.

Things to try:

1. Add a `transfer(self, other, amount)` method.
2. Print `a` directly. Not very helpful: the next lesson fixes that.
3. Add a class attribute `bank = "IIIT Bank"` and print it from both objects.

## Exercise

Write a class `Stack` with methods `push(x)`, `pop()` (returns the top item, or `None` if empty), `peek()` (top item without removing it, or `None`) and `size()`. The program below reads commands and uses it.

```input
6
push 4
push 7
peek
pop
pop
pop
```

```python starter
class Stack:
    pass


s = Stack()
for _ in range(int(input())):
    cmd = input().split()
    if cmd[0] == "push":
        s.push(int(cmd[1]))
    elif cmd[0] == "pop":
        print(s.pop())
    elif cmd[0] == "peek":
        print(s.peek())
print("size", s.size())
```

```python solution
class Stack:
    def __init__(self):
        self.items = []

    def push(self, x):
        self.items.append(x)

    def pop(self):
        return self.items.pop() if self.items else None

    def peek(self):
        return self.items[-1] if self.items else None

    def size(self):
        return len(self.items)


s = Stack()
for _ in range(int(input())):
    cmd = input().split()
    if cmd[0] == "push":
        s.push(int(cmd[1]))
    elif cmd[0] == "pop":
        print(s.pop())
    elif cmd[0] == "peek":
        print(s.peek())
print("size", s.size())
```

```tests
{"name": "example", "stdin": "6\npush 4\npush 7\npeek\npop\npop\npop\n", "expected": "7\n7\n4\nNone\nsize 0"}
{"name": "leaves items", "stdin": "3\npush 1\npush 2\npeek\n", "expected": "2\nsize 2"}
```
