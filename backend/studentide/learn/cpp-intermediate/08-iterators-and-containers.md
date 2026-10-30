---
title: Iterators, pairs and more containers
summary: begin and end, pair, tuple and structured bindings, deque and list, and binary search with lower_bound.
---
Every standard container gives **iterators**: `begin()` points at the first element and `end()` points *one past* the last. An iterator works like a pointer: `*it` is the element and `++it` moves on. The algorithms in `<algorithm>` all take a pair of iterators, so they work on any container.

```cpp
#include <algorithm>
#include <iostream>
#include <vector>

int main() {
    std::vector<int> v = {5, 3, 8, 1};
    for (auto it = v.begin(); it != v.end(); ++it) std::cout << *it << " ";
    std::cout << "\n";
    std::sort(v.begin(), v.end());
    std::reverse(v.begin() + 1, v.end());     // any range, not just the whole thing
    for (int x : v) std::cout << x << " ";    // range-for uses begin() and end() for you
    std::cout << "\n";
    return 0;
}
```

`std::pair<A, B>` holds two values (`.first`, `.second`) and `std::tuple` holds any number. **Structured bindings** unpack them into named variables. Pairs compare by first, then second, so sorting a vector of pairs just works.

```cpp
#include <algorithm>
#include <iostream>
#include <string>
#include <tuple>
#include <vector>

int main() {
    std::vector<std::pair<int, std::string>> scores = {{72, "Ravi"}, {91, "Asha"}, {72, "Dev"}};
    std::sort(scores.begin(), scores.end());
    for (const auto& [score, name] : scores) std::cout << name << " " << score << "\n";

    std::tuple<std::string, int, double> t = {"pen", 3, 9.5};
    auto [item, qty, price] = t;
    std::cout << item << " x" << qty << " = " << qty * price << "\n";
    return 0;
}
```

Picking a container:

- `std::vector`: the default. Fast to read and to add at the end.
- `std::deque`: like vector but also fast to add and remove at the **front** (`push_front`).
- `std::list`: a linked list. Inserting in the middle is fast if you already have an iterator there, but you can't jump to element `i`.
- `std::map` / `std::set`: kept sorted (earlier lesson).

On a **sorted** range, `std::lower_bound(b, e, x)` returns an iterator to the first element `>= x`, and `std::upper_bound` to the first element `> x`. Both use binary search, so they are fast. Subtracting `begin()` turns an iterator into a position.

```cpp
#include <algorithm>
#include <iostream>
#include <vector>

int main() {
    std::vector<int> v = {1, 3, 3, 3, 7, 9};
    auto lo = std::lower_bound(v.begin(), v.end(), 3);
    auto hi = std::upper_bound(v.begin(), v.end(), 3);
    std::cout << "3 appears " << (hi - lo) << " times, first at " << (lo - v.begin()) << "\n";
    return 0;
}
```

Things to try:

1. Sort `scores` from highest to lowest with `std::sort(scores.rbegin(), scores.rend())`.
2. Use a `std::deque<int>` and `push_front` to print the numbers 1 to 5 in reverse.
3. What does `lower_bound` return for 10, which is bigger than everything?

## Exercise

Read `n` numbers and then `q` queries. For each query `x`, print how many of the numbers are less than or equal to `x`. Sort once, then use `upper_bound` for each query.

```input
5
7 2 9 4 4
3
4 1 10
```

```cpp starter
#include <iostream>
#include <vector>

int main() {
    int n;
    std::cin >> n;
    std::vector<int> v(n);
    for (int& x : v) std::cin >> x;
    return 0;
}
```

```cpp solution
#include <algorithm>
#include <iostream>
#include <vector>

int main() {
    int n, q, x;
    std::cin >> n;
    std::vector<int> v(n);
    for (int& e : v) std::cin >> e;
    std::sort(v.begin(), v.end());
    std::cin >> q;
    while (q--) {
        std::cin >> x;
        std::cout << (std::upper_bound(v.begin(), v.end(), x) - v.begin()) << "\n";
    }
    return 0;
}
```

```tests
{"name": "example", "stdin": "5\n7 2 9 4 4\n3\n4 1 10\n", "expected": "3\n0\n5"}
{"name": "exact", "stdin": "3\n1 2 3\n2\n2 3\n", "expected": "2\n3"}
{"name": "negatives", "stdin": "4\n-3 -1 0 5\n2\n-2 0\n", "expected": "1\n3", "hidden": true}
```
