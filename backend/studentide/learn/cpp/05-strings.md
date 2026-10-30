---
title: std::string
summary: Text that grows by itself: joining, comparing, searching and getline.
---
`std::string` (from `<string>`) is text that manages its own memory. Unlike C strings, you can join strings with `+`, compare them with `==` and `<`, and never worry about the `'\0'` or the buffer size.

```cpp
#include <iostream>
#include <string>

int main() {
    std::string first = "Ada", last = "Lovelace";
    std::string full = first + " " + last;
    std::cout << full << " has " << full.size() << " characters\n";

    std::cout << full[0] << full.back() << "\n";        // A e
    std::cout << full.substr(4, 4) << "\n";             // Love
    std::cout << full.find("lace") << "\n";             // 10
    if (full.find("xyz") == std::string::npos) {
        std::cout << "not found\n";
    }
    full += "!";
    std::cout << full << " " << (first < last) << "\n";

    std::string line;
    std::getline(std::cin, line);                       // a whole line, spaces and all
    std::cout << "you typed: [" << line << "]\n";
    return 0;
}
```

- `size()` (or `length()`) is the number of characters; `s[i]` reads one.
- `find` returns the position, or `std::string::npos` if it isn't there.
- `std::getline(std::cin, s)` reads a whole line. Careful: after `cin >> x`, the newline is still waiting, so call `std::cin.ignore()` before `getline`.
- `std::to_string(42)` makes a number into text; `std::stoi("42")` goes the other way.

Things to try:

1. Loop over the characters with `for (char c : full)` and count the vowels.
2. Use `toupper` (from `<cctype>`) to print the line in capitals.
3. Read a number with `cin >>` and then a line with `getline` without `ignore()`. What happens?

## Exercise

Read one line and print it with every word's letters reversed but the words kept in their order, separated by single spaces. (`std::istringstream` from `<sstream>` splits a line into words with `>>`.)

```input
hello world from cpp
```

```cpp starter
#include <iostream>
#include <sstream>
#include <string>

int main() {
    std::string line;
    std::getline(std::cin, line);
    // reverse each word
    return 0;
}
```

```cpp solution
#include <algorithm>
#include <iostream>
#include <sstream>
#include <string>

int main() {
    std::string line, word;
    std::getline(std::cin, line);
    std::istringstream in(line);
    bool first = true;
    while (in >> word) {
        std::reverse(word.begin(), word.end());
        std::cout << (first ? "" : " ") << word;
        first = false;
    }
    std::cout << "\n";
    return 0;
}
```

```tests
{"name": "four words", "stdin": "hello world from cpp\n", "expected": "olleh dlrow morf ppc"}
{"name": "one word", "stdin": "abc\n", "expected": "cba"}
{"name": "extra spaces", "stdin": "  ab   cd \n", "expected": "ba dc", "hidden": true}
```
