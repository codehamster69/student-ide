---
title: Recursion and backtracking
summary: Functions that call themselves, the base case, and trying every choice with backtracking.
---
A **recursive** function solves a problem by calling itself on a smaller version of it. Every recursive function needs a **base case** that stops the calls, or it recurses until the program runs out of stack and crashes.

```cpp
#include <iostream>

long long factorial(int n) {
    if (n <= 1) return 1;            // base case
    return n * factorial(n - 1);     // smaller problem
}

int digit_sum(int n) {
    if (n < 10) return n;
    return n % 10 + digit_sum(n / 10);
}

int main() {
    std::cout << factorial(10) << " " << digit_sum(4729) << "\n";
    return 0;
}
```

Recursion shines when a problem branches. **Backtracking** builds an answer one choice at a time: make a choice, recurse to fill in the rest, then undo the choice and try the next one. This prints every subset of `{a, b, c}`:

```cpp
#include <iostream>
#include <string>

void subsets(const std::string& items, int i, std::string& chosen) {
    if (i == (int)items.size()) {            // every item decided
        std::cout << "{" << chosen << "}\n";
        return;
    }
    subsets(items, i + 1, chosen);           // leave items[i] out
    chosen.push_back(items[i]);              // take it...
    subsets(items, i + 1, chosen);
    chosen.pop_back();                       // ...and undo
}

int main() {
    std::string chosen;
    subsets("abc", 0, chosen);
    return 0;
}
```

With `n` items there are `2^n` subsets, so backtracking is slow for large `n`; that is the nature of trying everything.

Things to try:

1. Remove the base case from `factorial` and run it. Read the error.
2. Make `subsets` print only subsets with exactly two items.
3. Swap the order of "leave out" and "take" in `subsets`. How does the output order change?

## Exercise

Read `n` (1 to 8) and print every string of `n` characters made of `0` and `1` that has **no two `1`s next to each other**, in increasing order, one per line. Use backtracking.

```input
3
```

```cpp starter
#include <iostream>
#include <string>

int main() {
    int n;
    std::cin >> n;
    return 0;
}
```

```cpp solution
#include <iostream>
#include <string>

void build(int n, std::string& s) {
    if ((int)s.size() == n) {
        std::cout << s << "\n";
        return;
    }
    s.push_back('0');
    build(n, s);
    s.pop_back();
    if (s.empty() || s.back() != '1') {
        s.push_back('1');
        build(n, s);
        s.pop_back();
    }
}

int main() {
    int n;
    std::cin >> n;
    std::string s;
    build(n, s);
    return 0;
}
```

```tests
{"name": "3", "stdin": "3\n", "expected": "000\n001\n010\n100\n101"}
{"name": "1", "stdin": "1\n", "expected": "0\n1"}
{"name": "2", "stdin": "2\n", "expected": "00\n01\n10"}
{"name": "4", "stdin": "4\n", "expected": "0000\n0001\n0010\n0100\n0101\n1000\n1001\n1010", "hidden": true}
```
