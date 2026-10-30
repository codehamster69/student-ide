---
title: Decisions and loops
summary: if, switch, for, while, and the range-based for loop.
---
`if`, `else`, `switch`, `for`, `while` and `do ... while` work exactly as in C. C++ adds the **range-based for**, which visits every element of a collection without an index:

```cpp
#include <iostream>

int main() {
    int n;
    std::cin >> n;

    if (n % 2 == 0) {
        std::cout << n << " is even\n";
    } else {
        std::cout << n << " is odd\n";
    }

    for (int i = 1; i <= n; i++) {          // the classic loop
        std::cout << i << (i < n ? " " : "\n");
    }

    int primes[] = {2, 3, 5, 7, 11};
    for (int p : primes) {                  // range-based for
        std::cout << p * p << " ";
    }
    std::cout << "\n";

    int steps = 0;
    while (n != 1 && n > 0) {               // a while loop
        n = (n % 2 == 0) ? n / 2 : 3 * n + 1;
        steps++;
    }
    std::cout << "steps to reach 1: " << steps << "\n";
    return 0;
}
```

Things to try:

1. Change the input number and run again.
2. Print only the primes above 4 using `continue` inside the range-based loop.
3. Write a `switch` that prints the name of a weekday from a number 1-7.

## Exercise

Read `n` and print a multiplication table for 1 to `n`: `n` lines, each with `n` numbers separated by single spaces (line `i` holds `i*1 i*2 ... i*n`).

```input
4
```

```cpp starter
#include <iostream>

int main() {
    int n;
    std::cin >> n;
    // print the n x n table
    return 0;
}
```

```cpp solution
#include <iostream>

int main() {
    int n;
    std::cin >> n;
    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= n; j++) {
            std::cout << i * j << (j < n ? " " : "\n");
        }
    }
    return 0;
}
```

```tests
{"name": "4", "stdin": "4\n", "expected": "1 2 3 4\n2 4 6 8\n3 6 9 12\n4 8 12 16"}
{"name": "1", "stdin": "1\n", "expected": "1"}
{"name": "2", "stdin": "2\n", "expected": "1 2\n2 4", "hidden": true}
```
