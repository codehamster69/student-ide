---
title: Inheritance and virtual functions
summary: Base classes, derived classes, and calling the right function at run time.
---
A class can **inherit** from another: the derived class gets the base class's members and adds its own. Marking a member function `virtual` lets a derived class **override** it, and a call through a base-class pointer or reference then runs the derived version. This is *polymorphism*.

```cpp
#include <iostream>
#include <memory>
#include <string>
#include <vector>

class Shape {
public:
    virtual ~Shape() = default;                 // always virtual in a base class
    virtual double area() const = 0;            // = 0: pure virtual, must be overridden
    virtual std::string name() const { return "shape"; }
};

class Circle : public Shape {
public:
    explicit Circle(double r) : r_(r) {}
    double area() const override { return 3.14159 * r_ * r_; }
    std::string name() const override { return "circle"; }
private:
    double r_;
};

class Square : public Shape {
public:
    explicit Square(double s) : s_(s) {}
    double area() const override { return s_ * s_; }
private:
    double s_;
};

int main() {
    std::vector<std::unique_ptr<Shape>> shapes;
    shapes.push_back(std::make_unique<Circle>(1));
    shapes.push_back(std::make_unique<Square>(3));
    for (const auto &s : shapes) {
        std::cout << s->name() << " " << s->area() << "\n";   // picks the right one at run time
    }
    return 0;
}
```

- A class with a pure virtual function (`= 0`) is **abstract**: you can't make an object of it directly.
- `override` asks the compiler to check that you really override something. A typo in the name or a missing `const` becomes an error instead of a silent new function.
- A base class used through pointers needs a `virtual` destructor, or deleting a derived object through a base pointer skips the derived destructor.
- Containers of different shapes hold *pointers* (here `std::unique_ptr<Shape>`), since a `Shape` value can't hold a `Circle`.

Things to try:

1. Remove `virtual` from `name()` in `Shape`. What does the square print now? And the circle?
2. Try `Shape s;`. Read the error.
3. Add a `Triangle` class.

## Exercise

Build an employee payroll. `Employee` is an abstract base with a name and a pure virtual `double pay() const`. `Salaried` gets a monthly salary; `Hourly` gets `hours * rate`, with hours above 160 paid 1.5 times the rate. Each input line is `S name salary` or `H name hours rate`. Print each `name pay` (two decimals), then `total X`.

```input
3
S asha 50000
H ravi 170 200
H neel 100 250
```

```cpp starter
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

class Employee {
public:
    explicit Employee(std::string name) : name_(std::move(name)) {}
    virtual ~Employee() = default;
    const std::string &name() const { return name_; }
private:
    std::string name_;
};

// class Salaried, class Hourly

int main() {
    int n;
    std::cin >> n;
    std::vector<std::unique_ptr<Employee>> staff;
    for (int i = 0; i < n; i++) {
        char kind;
        std::string name;
        std::cin >> kind >> name;
        // read the rest and add the right kind of employee
    }
    double total = 0;
    std::cout << std::fixed << std::setprecision(2);
    for (const auto &e : staff) {
        std::cout << e->name() << " " << e->pay() << "\n";
        total += e->pay();
    }
    std::cout << "total " << total << "\n";
    return 0;
}
```

```cpp solution
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

class Employee {
public:
    explicit Employee(std::string name) : name_(std::move(name)) {}
    virtual ~Employee() = default;
    const std::string &name() const { return name_; }
    virtual double pay() const = 0;
private:
    std::string name_;
};

class Salaried : public Employee {
public:
    Salaried(std::string name, double salary) : Employee(std::move(name)), salary_(salary) {}
    double pay() const override { return salary_; }
private:
    double salary_;
};

class Hourly : public Employee {
public:
    Hourly(std::string name, double hours, double rate) : Employee(std::move(name)), hours_(hours), rate_(rate) {}
    double pay() const override {
        double extra = hours_ > 160 ? hours_ - 160 : 0;
        return (hours_ - extra) * rate_ + extra * rate_ * 1.5;
    }
private:
    double hours_, rate_;
};

int main() {
    int n;
    std::cin >> n;
    std::vector<std::unique_ptr<Employee>> staff;
    for (int i = 0; i < n; i++) {
        char kind;
        std::string name;
        std::cin >> kind >> name;
        if (kind == 'S') {
            double salary;
            std::cin >> salary;
            staff.push_back(std::make_unique<Salaried>(name, salary));
        } else {
            double hours, rate;
            std::cin >> hours >> rate;
            staff.push_back(std::make_unique<Hourly>(name, hours, rate));
        }
    }
    double total = 0;
    std::cout << std::fixed << std::setprecision(2);
    for (const auto &e : staff) {
        std::cout << e->name() << " " << e->pay() << "\n";
        total += e->pay();
    }
    std::cout << "total " << total << "\n";
    return 0;
}
```

```tests
{"name": "example", "stdin": "3\nS asha 50000\nH ravi 170 200\nH neel 100 250\n", "expected": "asha 50000.00\nravi 35000.00\nneel 25000.00\ntotal 110000.00"}
{"name": "exactly 160 hours", "stdin": "1\nH zoya 160 100\n", "expected": "zoya 16000.00\ntotal 16000.00", "hidden": true}
```
