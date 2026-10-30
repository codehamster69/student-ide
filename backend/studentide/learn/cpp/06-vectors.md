---
title: Vectors
summary: std::vector, the array that grows, and the most used container in C++.
---
`std::vector<T>` (from `<vector>`) is an array that knows its size and grows when you add to it. You get array speed without managing memory yourself.

```cpp
#include <iostream>
#include <vector>

int main() {
    std::vector<int> marks = {72, 85, 64};
    marks.push_back(90);                 // add at the end
    marks.push_back(58);

    std::cout << "size " << marks.size() << ", first " << marks[0]
              << ", last " << marks.back() << "\n";

    int total = 0;
    for (int m : marks) total += m;
    std::cout << "average " << total / double(marks.size()) << "\n";

    marks.pop_back();                    // remove the last one
    marks[1] = 88;                       // change one
    for (std::size_t i = 0; i < marks.size(); i++) {
        std::cout << i << ": " << marks.at(i) << "\n";
    }

    std::vector<std::vector<int>> grid(3, std::vector<int>(4, 0));   // 3 x 4 of zeros
    grid[1][2] = 7;
    std::cout << grid[1][2] << "\n";
    return 0;
}
```

- `v[i]` doesn't check the index (like C arrays); `v.at(i)` does and throws an error if it's out of range. Try `marks.at(10)`.
- `std::vector<int> v(n);` makes `n` zeros; `v(n, x)` makes `n` copies of `x`.
- Pass vectors to functions by `const &` to avoid copying them.

Things to try:

1. Read `n` numbers from the input into a vector with `push_back`.
2. Write `int largest(const std::vector<int> &v)`.
3. Print `marks.size()` after each `push_back`. Also print `marks.capacity()`: the vector reserves extra room as it grows.

## Exercise

The input is `n` followed by `n` whole numbers. Print the numbers with duplicates removed, keeping the **first** occurrence of each and the original order, separated by spaces.

```input
8
3 1 3 2 1 5 2 3
```

```cpp starter
#include <iostream>
#include <vector>

int main() {
    int n;
    std::cin >> n;
    std::vector<int> v(n);
    for (int &x : v) std::cin >> x;
    // print v without repeats, first occurrences in order
    return 0;
}
```

```cpp solution
#include <iostream>
#include <vector>

int main() {
    int n;
    std::cin >> n;
    std::vector<int> v(n);
    for (int &x : v) std::cin >> x;
    std::vector<int> seen;
    for (int x : v) {
        bool found = false;
        for (int y : seen) {
            if (y == x) found = true;
        }
        if (!found) seen.push_back(x);
    }
    for (std::size_t i = 0; i < seen.size(); i++) {
        std::cout << seen[i] << (i + 1 < seen.size() ? " " : "\n");
    }
    return 0;
}
```

```tests
{"name": "example", "stdin": "8\n3 1 3 2 1 5 2 3\n", "expected": "3 1 2 5"}
{"name": "no repeats", "stdin": "3\n7 8 9\n", "expected": "7 8 9"}
{"name": "all same", "stdin": "4\n6 6 6 6\n", "expected": "6", "hidden": true}
```
