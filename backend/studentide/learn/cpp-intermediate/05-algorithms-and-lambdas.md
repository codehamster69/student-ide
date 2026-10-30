---
title: Algorithms and lambdas
summary: sort, find_if, count_if, accumulate and transform, with lambdas.
---
`<algorithm>` and `<numeric>` hold ready-made, well-tested loops. They work on a *range*, given as two iterators: `v.begin()` (the first element) and `v.end()` (just past the last). A **lambda** is a small function written right where it is used: `[](int x) { return x % 2 == 0; }`.

```cpp
#include <algorithm>
#include <iostream>
#include <numeric>
#include <vector>

int main() {
    std::vector<int> v = {7, 2, 9, 4, 1, 8};

    std::sort(v.begin(), v.end());                              // 1 2 4 7 8 9
    std::sort(v.begin(), v.end(), [](int a, int b) { return a > b; });   // descending

    int evens = std::count_if(v.begin(), v.end(), [](int x) { return x % 2 == 0; });
    int sum = std::accumulate(v.begin(), v.end(), 0);
    auto big = std::find_if(v.begin(), v.end(), [](int x) { return x < 5; });
    int limit = 5;
    bool all_small = std::all_of(v.begin(), v.end(), [limit](int x) { return x < limit; });

    std::vector<int> squares(v.size());
    std::transform(v.begin(), v.end(), squares.begin(), [](int x) { return x * x; });

    std::cout << evens << " " << sum << " " << *big << " " << all_small << "\n";
    for (int s : squares) std::cout << s << " ";
    std::cout << "\n" << *std::max_element(v.begin(), v.end()) << "\n";
    return 0;
}
```

- The `[ ]` at the start of a lambda is its **capture list**: `[limit]` copies `limit` into the lambda, `[&total]` lets it change `total`, `[=]`/`[&]` capture everything used.
- Prefer an algorithm over a hand-written loop when one fits: the name says what the loop does.
- Other useful ones: `reverse`, `unique`, `binary_search`, `min_element`, `iota`, `stable_sort`.

Things to try:

1. Remove the duplicates of a sorted vector with `v.erase(std::unique(v.begin(), v.end()), v.end());`.
2. Count the words longer than 3 letters in a `std::vector<std::string>`.
3. Use a lambda with `[&total]` to sum inside `std::for_each`.

## Exercise

The input is `n` and then `n` lines of `name marks`. Sort the students by marks, highest first; equal marks by name. Print them as `rank name marks`, then a last line `average X` with one decimal. Use `std::sort` with a lambda and `std::accumulate`.

```input
4
ravi 78
asha 91
neel 78
zoya 85
```

```cpp starter
#include <algorithm>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

struct Student {
    std::string name;
    int marks;
};

int main() {
    int n;
    std::cin >> n;
    std::vector<Student> s(n);
    for (auto &x : s) std::cin >> x.name >> x.marks;
    // sort, print ranks, print the average
    return 0;
}
```

```cpp solution
#include <algorithm>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

struct Student {
    std::string name;
    int marks;
};

int main() {
    int n;
    std::cin >> n;
    std::vector<Student> s(n);
    for (auto &x : s) std::cin >> x.name >> x.marks;
    std::sort(s.begin(), s.end(), [](const Student &a, const Student &b) {
        return a.marks != b.marks ? a.marks > b.marks : a.name < b.name;
    });
    for (int i = 0; i < n; i++) {
        std::cout << i + 1 << " " << s[i].name << " " << s[i].marks << "\n";
    }
    int total = std::accumulate(s.begin(), s.end(), 0, [](int t, const Student &x) { return t + x.marks; });
    std::cout << "average " << std::fixed << std::setprecision(1) << double(total) / n << "\n";
    return 0;
}
```

```tests
{"name": "example", "stdin": "4\nravi 78\nasha 91\nneel 78\nzoya 85\n", "expected": "1 asha 91\n2 zoya 85\n3 neel 78\n4 ravi 78\naverage 83.0"}
{"name": "one", "stdin": "1\nsolo 50\n", "expected": "1 solo 50\naverage 50.0", "hidden": true}
```
