---
title: Maps and sets
summary: std::map, std::unordered_map and std::set for lookups and counting.
---
A **`std::map<K, V>`** stores key → value pairs, sorted by key. A **`std::set<T>`** stores unique values, sorted. The `unordered_` versions use hashing: usually faster, but in no particular order.

```cpp
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <unordered_map>

int main() {
    std::map<std::string, int> marks;
    marks["ravi"] = 78;
    marks["asha"] = 91;
    marks["neel"] = 85;
    for (const auto &[name, m] : marks) {          // sorted by name
        std::cout << name << " " << m << "\n";
    }
    std::cout << marks.count("zoya") << "\n";      // 0: not there
    if (auto it = marks.find("asha"); it != marks.end()) {
        std::cout << "found asha: " << it->second << "\n";
    }

    std::unordered_map<char, int> freq;
    for (char c : std::string("mississippi")) freq[c]++;   // missing keys start at 0
    std::cout << "s appears " << freq['s'] << " times\n";

    std::set<int> seen = {5, 1, 5, 3, 1};
    seen.insert(4);
    for (int x : seen) std::cout << x << " ";      // 1 3 4 5
    std::cout << "\n";
    return 0;
}
```

- `m[key]` creates the key (with a zero/empty value) if it isn't there. Use `count` or `find` to check without creating.
- `const auto &[name, m]` is a *structured binding*: it unpacks each pair.
- Lookups in `map`/`set` take about log₂(n) steps; in the `unordered_` versions, about one step on average.

Things to try:

1. Print the letters of "mississippi" with their counts in alphabetical order (use a `std::map` instead).
2. Erase a key with `marks.erase("ravi")`.
3. Use `std::multiset` and insert duplicates. What changes?

## Exercise

Read `n` and then `n` words. Print each distinct word and how many times it appeared, in alphabetical order, as `word count`. Then print on a last line the word that appeared most often (the alphabetically first one if there is a tie).

```input
7
apple pear apple fig pear apple kiwi
```

```cpp starter
#include <iostream>
#include <map>
#include <string>

int main() {
    int n;
    std::cin >> n;
    // count the words
    return 0;
}
```

```cpp solution
#include <iostream>
#include <map>
#include <string>

int main() {
    int n;
    std::cin >> n;
    std::map<std::string, int> count;
    for (int i = 0; i < n; i++) {
        std::string w;
        std::cin >> w;
        count[w]++;
    }
    std::string best;
    int most = 0;
    for (const auto &[word, c] : count) {
        std::cout << word << " " << c << "\n";
        if (c > most) {
            most = c;
            best = word;
        }
    }
    std::cout << best << "\n";
    return 0;
}
```

```tests
{"name": "fruit", "stdin": "7\napple pear apple fig pear apple kiwi\n", "expected": "apple 3\nfig 1\nkiwi 1\npear 2\napple"}
{"name": "tie", "stdin": "4\nb a b a\n", "expected": "a 2\nb 2\na"}
{"name": "one", "stdin": "1\nsolo\n", "expected": "solo 1\nsolo", "hidden": true}
```
