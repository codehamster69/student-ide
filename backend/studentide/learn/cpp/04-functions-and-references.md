---
title: Functions and references
summary: Pass by value or by reference, const references, overloading and default arguments.
---
Functions look like C functions, with three useful additions.

**References.** A parameter declared `int &x` is another name for the caller's variable, so the function can change it, without pointers:

```cpp
#include <iostream>
#include <string>

void add_bonus(int &marks, int bonus = 5) {   // bonus has a default value
    marks += bonus;
}

// const & : no copy is made, and the function promises not to change it
void greet(const std::string &name) {
    std::cout << "Hello, " << name << "\n";
}

// overloading: same name, different parameter types
int biggest(int a, int b) { return a > b ? a : b; }
double biggest(double a, double b) { return a > b ? a : b; }

int main() {
    int m = 70;
    add_bonus(m);          // uses the default bonus of 5
    add_bonus(m, 10);
    std::cout << m << "\n";              // 85
    greet("Meera");
    std::cout << biggest(3, 9) << " " << biggest(2.5, 1.5) << "\n";
    return 0;
}
```

- Pass small values (`int`, `double`) **by value**.
- Pass something the function must change **by reference** (`T &`).
- Pass big things the function only reads (strings, vectors) **by const reference** (`const T &`): no copying.
- Overloads are chosen by the argument types. Default arguments go at the end of the parameter list.

Things to try:

1. Remove the `&` from `add_bonus`. What does `m` print now?
2. Add an overload `biggest(int a, int b, int c)`.
3. Try to change `name` inside `greet`. Read the error.

## Exercise

Write `void sort3(int &a, int &b, int &c)` that rearranges its three arguments so that `a <= b <= c`. Use `std::swap(x, y)` if you like. `main` reads three numbers, calls it and prints them.

```input
9 2 5
```

```cpp starter
#include <iostream>
#include <utility>

void sort3(int &a, int &b, int &c) {
    // put a, b, c in increasing order
}

int main() {
    int a, b, c;
    std::cin >> a >> b >> c;
    sort3(a, b, c);
    std::cout << a << " " << b << " " << c << "\n";
    return 0;
}
```

```cpp solution
#include <iostream>
#include <utility>

void sort3(int &a, int &b, int &c) {
    if (a > b) std::swap(a, b);
    if (b > c) std::swap(b, c);
    if (a > b) std::swap(a, b);
}

int main() {
    int a, b, c;
    std::cin >> a >> b >> c;
    sort3(a, b, c);
    std::cout << a << " " << b << " " << c << "\n";
    return 0;
}
```

```tests
{"name": "9 2 5", "stdin": "9 2 5\n", "expected": "2 5 9"}
{"name": "reversed", "stdin": "3 2 1\n", "expected": "1 2 3"}
{"name": "repeats", "stdin": "4 1 4\n", "expected": "1 4 4", "hidden": true}
```
