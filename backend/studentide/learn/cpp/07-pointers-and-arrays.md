---
title: Pointers, arrays and new
summary: Raw arrays and std::array, pointers and nullptr, new and delete, and why vector is usually better.
---
C++ keeps C's **built-in arrays** (fixed size, no bounds checks, they forget their size when passed to a function). `std::array<T, N>` is the safer fixed-size version: it knows its size, can be copied, and has `.at(i)`, which checks the index.

```cpp
#include <array>
#include <iostream>

int main() {
    int raw[4] = {3, 1, 4, 1};
    std::array<int, 4> a = {3, 1, 4, 1};
    std::cout << "raw[2] = " << raw[2] << ", a.size() = " << a.size() << "\n";
    for (int x : a) std::cout << x << " ";
    std::cout << "\n";
    // a.at(10) throws std::out_of_range; raw[10] silently reads garbage
    return 0;
}
```

A **pointer** holds an address. `&x` gives the address of `x`, and `*p` gives the thing `p` points to. A pointer that points nowhere should be `nullptr`. Always check before you use `*p`.

```cpp
#include <iostream>

int main() {
    int x = 10;
    int* p = &x;
    *p = 20;                       // changes x through p
    std::cout << x << "\n";

    int* q = nullptr;
    if (q == nullptr) std::cout << "q points nowhere\n";

    int nums[] = {5, 6, 7};
    int* it = nums;                // an array name turns into a pointer to its first element
    std::cout << *(it + 2) << "\n";  // 7, the same as nums[2]
    return 0;
}
```

**References versus pointers**: a reference (`int& r = x;`) is another name for an existing object; it can't be null and can't be pointed elsewhere. A pointer can be null and can be moved. Use references for parameters unless "nothing" is a valid value.

`new` creates an object on the heap and `delete` destroys it; `new T[n]` needs `delete[]`. Forgetting `delete` leaks memory, and deleting twice crashes. In modern C++ you rarely write `new` yourself: use `std::vector` for arrays and smart pointers (an advanced lesson) for single objects.

```cpp
#include <iostream>

int main() {
    int n = 5;
    int* squares = new int[n];
    for (int i = 0; i < n; i++) squares[i] = i * i;
    std::cout << squares[4] << "\n";
    delete[] squares;              // every new[] needs exactly one delete[]
    return 0;
}
```

Things to try:

1. Replace `a.at(10)` in a comment with a real call and run it.
2. Print `p` itself (an address) and `*p`.
3. Change `delete[]` to `delete`. The compiler may not complain, but it is wrong. Why?

## Exercise

Write `int* find_first(int* begin, int* end, int x)`. It looks at the elements from `begin` up to (not including) `end` and returns a pointer to the first one equal to `x`, or `nullptr` if there is none. The given `main` reads `n` numbers and queries, and prints the position found or `-1`.

```input
5
4 8 15 16 23
3
15 4 42
```

```cpp starter
#include <iostream>
#include <vector>

int* find_first(int* begin, int* end, int x) {
    return nullptr;
}

int main() {
    int n, q, x;
    std::cin >> n;
    std::vector<int> v(n);
    for (int& e : v) std::cin >> e;
    std::cin >> q;
    while (q--) {
        std::cin >> x;
        int* p = find_first(v.data(), v.data() + n, x);
        std::cout << (p ? p - v.data() : -1) << "\n";
    }
    return 0;
}
```

```cpp solution
#include <iostream>
#include <vector>

int* find_first(int* begin, int* end, int x) {
    for (int* p = begin; p != end; ++p) {
        if (*p == x) return p;
    }
    return nullptr;
}

int main() {
    int n, q, x;
    std::cin >> n;
    std::vector<int> v(n);
    for (int& e : v) std::cin >> e;
    std::cin >> q;
    while (q--) {
        std::cin >> x;
        int* p = find_first(v.data(), v.data() + n, x);
        std::cout << (p ? p - v.data() : -1) << "\n";
    }
    return 0;
}
```

```tests
{"name": "example", "stdin": "5\n4 8 15 16 23\n3\n15 4 42\n", "expected": "2\n0\n-1"}
{"name": "first of repeats", "stdin": "4\n7 3 7 3\n1\n3\n", "expected": "1"}
{"name": "last", "stdin": "3\n1 2 3\n1\n3\n", "expected": "2", "hidden": true}
```
