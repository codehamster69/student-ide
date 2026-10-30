---
title: Classes
summary: Data and the functions that use it, with public and private parts.
---
A **class** groups data (*member variables*) with the functions that work on it (*member functions*). Members marked `private` can only be touched by the class's own functions, so the class can protect its rules.

```cpp
#include <iostream>
#include <string>

class BankAccount {
public:
    BankAccount(std::string owner, double balance)      // constructor
        : owner_(owner), balance_(balance) {}

    void deposit(double amount) {
        if (amount > 0) balance_ += amount;
    }
    bool withdraw(double amount) {
        if (amount > balance_) return false;            // the rule: no overdraft
        balance_ -= amount;
        return true;
    }
    double balance() const { return balance_; }         // const: doesn't change the object
    const std::string &owner() const { return owner_; }

private:
    std::string owner_;
    double balance_;
};

int main() {
    BankAccount a("asha", 100);
    a.deposit(50);
    std::cout << a.withdraw(500) << " " << a.withdraw(30) << "\n";   // 0 1
    std::cout << a.owner() << " has " << a.balance() << "\n";
    // a.balance_ = 1e9;   // error: balance_ is private
    return 0;
}
```

- A **constructor** has the class's name and no return type. The `: owner_(owner), balance_(balance)` part is the *member initializer list*.
- A `const` member function promises not to change the object, so it can be called on `const` objects.
- `struct` is the same as `class` except that members are public by default.

Things to try:

1. Uncomment the `a.balance_` line and read the error.
2. Add a `transfer(BankAccount &to, double amount)` member function.
3. Remove `const` from `balance()` and call it on a `const BankAccount`.

## Exercise

Complete the class `Rectangle` with a constructor taking width and height, and `const` member functions `area()`, `perimeter()` and `is_square()`. `main` reads rectangles and prints, for each, `area perimeter square|not square`.

```input
2
4 5
3 3
```

```cpp starter
#include <iostream>

class Rectangle {
public:
    // constructor and member functions
private:
    double w_, h_;
};

int main() {
    int n;
    std::cin >> n;
    for (int i = 0; i < n; i++) {
        double w, h;
        std::cin >> w >> h;
        Rectangle r(w, h);
        std::cout << r.area() << " " << r.perimeter() << " "
                  << (r.is_square() ? "square" : "not square") << "\n";
    }
    return 0;
}
```

```cpp solution
#include <iostream>

class Rectangle {
public:
    Rectangle(double w, double h) : w_(w), h_(h) {}
    double area() const { return w_ * h_; }
    double perimeter() const { return 2 * (w_ + h_); }
    bool is_square() const { return w_ == h_; }
private:
    double w_, h_;
};

int main() {
    int n;
    std::cin >> n;
    for (int i = 0; i < n; i++) {
        double w, h;
        std::cin >> w >> h;
        Rectangle r(w, h);
        std::cout << r.area() << " " << r.perimeter() << " "
                  << (r.is_square() ? "square" : "not square") << "\n";
    }
    return 0;
}
```

```tests
{"name": "example", "stdin": "2\n4 5\n3 3\n", "expected": "20 18 not square\n9 12 square"}
{"name": "decimals", "stdin": "1\n1.5 2\n", "expected": "3 7 not square", "hidden": true}
```
