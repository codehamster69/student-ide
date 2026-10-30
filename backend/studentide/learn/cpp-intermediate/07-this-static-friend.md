---
title: this, const members, static and friend
summary: The this pointer, member functions that promise not to change the object, members shared by the whole class, and friends.
---
Inside a member function, `this` points to the object the function was called on. You rarely need to write it, except to tell a member apart from a parameter with the same name, or to return the object itself so calls can be chained.

A member function marked `const` promises not to change the object. Only `const` functions can be called on a `const` object or through a `const&`, so mark every function that only reads.

```cpp
#include <iostream>
#include <string>

class Counter {
public:
    Counter& add(int n) { value += n; return *this; }   // return the object: chainable
    int get() const { return value; }                    // const: only reads
private:
    int value = 0;
};

void show(const Counter& c) { std::cout << c.get() << "\n"; }  // needs get() to be const

int main() {
    Counter c;
    c.add(2).add(3).add(5);
    show(c);
    return 0;
}
```

A **static** member belongs to the class, not to any one object: there is one copy shared by all objects. A static member function has no `this` and is called as `ClassName::function()`.

```cpp
#include <iostream>

class Ticket {
public:
    Ticket() : number(++issued) {}
    int id() const { return number; }
    static int total() { return issued; }
private:
    int number;
    static inline int issued = 0;   // one counter for the whole class (C++17)
};

int main() {
    Ticket a, b, c;
    std::cout << b.id() << " of " << Ticket::total() << "\n";
    return 0;
}
```

A **friend** function is not a member, but the class lets it see private members. The most common use is `operator<<` for printing, which can't be a member because its left side is the stream.

```cpp
#include <iostream>

class Point {
public:
    Point(int x, int y) : x(x), y(y) {}     // the member x is set from the parameter x
    friend std::ostream& operator<<(std::ostream& out, const Point& p) {
        return out << "(" << p.x << ", " << p.y << ")";
    }
private:
    int x, y;
};

int main() {
    std::cout << Point(3, 4) << "\n";
    return 0;
}
```

Things to try:

1. Remove `const` from `get()`. Why does `show` stop compiling?
2. Make `issued` a normal (non-static) member. What does `total()` print now, and why does the compiler object?
3. Remove `friend` from `operator<<`. Read the error.

## Exercise

Write a class `Account` with a constructor taking an owner's name and an opening balance, a `deposit(int)` member that returns `*this` so calls chain, a `const` member `balance()`, a static member function `count()` giving how many accounts were opened, and a friend `operator<<` that prints `name: balance`. The given `main` reads accounts and deposits.

```input
2
Asha 100 50
Ravi 20 0
```

```cpp starter
#include <iostream>
#include <string>
#include <vector>

class Account {
};

int main() {
    int n;
    std::cin >> n;
    std::vector<Account> all;
    for (int i = 0; i < n; i++) {
        std::string name;
        int open, dep;
        std::cin >> name >> open >> dep;
        all.emplace_back(name, open);
        all.back().deposit(dep).deposit(1);
    }
    for (const Account& a : all) std::cout << a << "\n";
    std::cout << Account::count() << " accounts\n";
    return 0;
}
```

```cpp solution
#include <iostream>
#include <string>
#include <vector>

class Account {
public:
    Account(std::string owner, int opening) : owner(std::move(owner)), money(opening) { ++opened; }
    Account& deposit(int amount) { money += amount; return *this; }
    int balance() const { return money; }
    static int count() { return opened; }
    friend std::ostream& operator<<(std::ostream& out, const Account& a) {
        return out << a.owner << ": " << a.money;
    }
private:
    std::string owner;
    int money;
    static inline int opened = 0;
};

int main() {
    int n;
    std::cin >> n;
    std::vector<Account> all;
    for (int i = 0; i < n; i++) {
        std::string name;
        int open, dep;
        std::cin >> name >> open >> dep;
        all.emplace_back(name, open);
        all.back().deposit(dep).deposit(1);
    }
    for (const Account& a : all) std::cout << a << "\n";
    std::cout << Account::count() << " accounts\n";
    return 0;
}
```

```tests
{"name": "two", "stdin": "2\nAsha 100 50\nRavi 20 0\n", "expected": "Asha: 151\nRavi: 21\n2 accounts"}
{"name": "one", "stdin": "1\nMeena 0 9\n", "expected": "Meena: 10\n1 accounts"}
{"name": "three", "stdin": "3\nA 1 1\nB 2 2\nC 3 3\n", "expected": "A: 3\nB: 5\nC: 7\n3 accounts", "hidden": true}
```
