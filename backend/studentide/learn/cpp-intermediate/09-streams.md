---
title: Streams: formatting, parsing and files
summary: iomanip for neat output, stringstream for taking lines apart, cerr for errors, and reading and writing files.
---
`std::cout` is one of many **streams**. All of them share the same `<<` and `>>` operators, so once you can use `cout` and `cin` you can use files and strings the same way.

`<iomanip>` controls how numbers look: `std::fixed` with `std::setprecision(n)` gives `n` decimals, and `std::setw(n)` pads the next item to `n` characters (use it for tables).

```cpp
#include <iomanip>
#include <iostream>

int main() {
    double prices[] = {9.5, 120.0, 3.25};
    std::cout << std::fixed << std::setprecision(2);
    for (double p : prices) std::cout << std::setw(8) << p << "\n";
    std::cerr << "this goes to the error stream, not the output\n";
    return 0;
}
```

`std::cerr` is for error messages. It is shown separately from normal output, so programs that read your output aren't confused by them.

`std::getline(std::cin, line)` reads a whole line. An `std::istringstream` then lets you read words and numbers out of that line with `>>`, just like `cin`. This is the cleanest way to handle input where each line has a different number of items. `std::ostringstream` goes the other way and builds a string with `<<`.

```cpp
#include <iostream>
#include <sstream>
#include <string>

int main() {
    std::string line;
    while (std::getline(std::cin, line)) {    // until the input ends
        std::istringstream in(line);
        int x, sum = 0, count = 0;
        while (in >> x) { sum += x; count++; }
        std::ostringstream out;
        out << count << " numbers, sum " << sum;
        std::cout << out.str() << "\n";
    }
    return 0;
}
```

```input
1 2 3
10 20
7
```

**Files** use `std::ofstream` (write) and `std::ifstream` (read) from `<fstream>`. The file is closed automatically when the stream object goes out of scope (RAII again). Check that it opened before using it.

```cpp
#include <fstream>
#include <iostream>
#include <string>

int main() {
    {
        std::ofstream out("notes.txt");
        out << "first line\n" << 42 << "\n";
    }                                    // closed here
    std::ifstream in("notes.txt");
    if (!in) { std::cerr << "could not open\n"; return 1; }
    std::string word;
    int n;
    std::getline(in, word);
    in >> n;
    std::cout << word << " / " << n + 1 << "\n";
    return 0;
}
```

Mixing `cin >> x` and `getline` is a classic trap: `>>` leaves the newline behind, so the next `getline` reads an empty line. Call `std::cin.ignore()` after `>>`, or read everything with `getline`.

Things to try:

1. Remove `std::fixed` from the first example. How do the numbers change?
2. Give the stringstream example a line with a word in it, like `4 five 6`. Where does it stop?
3. Open a file that does not exist with `ifstream` and check the error path.

## Exercise

Each input line holds a student's name followed by any number of marks. Print each name and their average mark with exactly one decimal, like `Asha 81.5`. A student with no marks has an average of `0.0`.

```input
Asha 80 83
Ravi 90 70 65
Dev
```

```cpp starter
#include <iostream>
#include <string>

int main() {
    std::string name;
    while (std::cin >> name) {
        std::cout << name << "\n";
    }
    return 0;
}
```

```cpp solution
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

int main() {
    std::string line;
    std::cout << std::fixed << std::setprecision(1);
    while (std::getline(std::cin, line)) {
        std::istringstream in(line);
        std::string name;
        if (!(in >> name)) continue;
        double sum = 0;
        int count = 0, mark;
        while (in >> mark) { sum += mark; count++; }
        std::cout << name << " " << (count ? sum / count : 0.0) << "\n";
    }
    return 0;
}
```

```tests
{"name": "example", "stdin": "Asha 80 83\nRavi 90 70 65\nDev\n", "expected": "Asha 81.5\nRavi 75.0\nDev 0.0"}
{"name": "one", "stdin": "Meena 100\n", "expected": "Meena 100.0"}
{"name": "rounding", "stdin": "X 1 2 2\nY 0 0 1\n", "expected": "X 1.7\nY 0.3", "hidden": true}
```
