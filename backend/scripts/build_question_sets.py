"""Builds the original question sets shipped with Student IDE
(studentide/providers/data/sets/*.json, served by providers/originals.py).

Each question is written here once: statement, starter code, a reference
solution in the set's language, and test inputs. Expected outputs come from
the small Python model of each question below, so editing an input never
needs a hand-computed answer; tests/test_question_sets.py then runs every
reference solution through grading.grade against those outputs.

    python backend/scripts/build_question_sets.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "studentide" / "providers" / "data" / "sets"
TABLES = ROOT / "thesis" / "latex" / "tables"

MAIN = """#include <stdio.h>

int main(void) {
    // Read the input, then print the answer.

    return 0;
}
"""


def q(ref, title, topic, level, prompt, solution, model, inputs, shown=2, starter=MAIN):
    """inputs: stdin strings; the first `shown` are visible examples, the rest hidden."""
    tests = [{"name": f"Example {i + 1}" if i < shown else f"Hidden {i - shown + 1}", "stdin": s,
              "expected": model(s), "hidden": i >= shown, "compare": "text"} for i, s in enumerate(inputs)]
    return {"ref": ref, "title": title, "topic": topic, "level": level, "prompt": prompt.strip() + "\n",
            "starter_code": starter, "sample_input": inputs[0], "tests": tests, "solution": solution.strip() + "\n"}


def lines(*xs) -> str:
    return "\n".join(map(str, xs)) + "\n"


# ---------------------------------------------------------------- models

def m_hello(s):
    return f"Hello, {s.split()[0]}! Welcome to the contest."


def m_clock(s):
    t = int(s)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def m_samosa(s):
    n, p = map(int, s.split())
    free = n // 4
    return lines(free, (n - free) * p).rstrip("\n")


def m_leap(s):
    y = int(s)
    return "YES" if y % 400 == 0 or (y % 4 == 0 and y % 100 != 0) else "NO"


def m_grade(s):
    m = int(s)
    if m < 0 or m > 100:
        return "INVALID"
    return "A" if m >= 90 else "B" if m >= 75 else "C" if m >= 60 else "D" if m >= 40 else "F"


def m_digits(s):
    return str(sum(map(int, s.strip())))


def m_chai(s):
    out = []
    for i in range(1, int(s) + 1):
        out.append("ChaiSamosa" if i % 15 == 0 else "Chai" if i % 3 == 0 else "Samosa" if i % 5 == 0 else str(i))
    return "\n".join(out)


def m_stairs(s):
    return "\n".join(" ".join(str(j) for j in range(1, i + 1)) for i in range(1, int(s) + 1))


def m_top(s):
    xs = list(map(int, s.split()))[1:]
    return f"{max(xs)} {xs.count(max(xs))}"


def m_reverse(s):
    xs = s.split()[1:]
    return " ".join(reversed(xs))


def m_palin(s):
    w = s.split()[0]
    return "YES" if w == w[::-1] else "NO"


def m_vowels(s):
    line = s.split("\n")[0]
    return str(sum(c in "aeiouAEIOU" for c in line))


def m_prime(s):
    def prime(n):
        if n < 2:
            return False
        i = 2
        while i * i <= n:
            if n % i == 0:
                return False
            i += 1
        return True
    ns = list(map(int, s.split()))[1:]
    return "\n".join("PRIME" if prime(n) else "NOT PRIME" for n in ns)


# ---------------------------------------------------------------- C fundamentals

C_FUNDAMENTALS = [
    q("c-hello", "Hello, Competitor!", "Input and output", "warm-up", """
Every contest starts with a greeting. Read one word, a name, and greet that person.

Input: one name (letters only, at most 50 characters).

Output: Hello, <name>! Welcome to the contest.

Example: input "Riya" prints Hello, Riya! Welcome to the contest.
""", r"""
#include <stdio.h>

int main(void) {
    char name[64];
    scanf("%63s", name);
    printf("Hello, %s! Welcome to the contest.\n", name);
    return 0;
}
""", m_hello, ["Riya\n", "Arjun\n", "A\n", "Bhagyashree\n", "Zoe\n"]),

    q("c-clock", "Stopwatch Display", "Operators", "warm-up", """
A stopwatch counts seconds. Show the time as HH:MM:SS, each part with two digits.

Input: one integer S, the number of seconds (0 <= S <= 359999).

Output: the time as HH:MM:SS, with leading zeros.

Example: 3725 is 1 hour, 2 minutes and 5 seconds, so print 01:02:05.

Hint: use / and %, and %02d in printf.
""", r"""
#include <stdio.h>

int main(void) {
    int s;
    scanf("%d", &s);
    printf("%02d:%02d:%02d\n", s / 3600, s % 3600 / 60, s % 60);
    return 0;
}
""", m_clock, ["3725\n", "59\n", "0\n", "3600\n", "86399\n", "359999\n", "600\n"]),

    q("c-samosa", "Samosa Offer", "Operators", "warm-up", """
The canteen has an offer: buy samosas and every 4th samosa is free.
Given how many samosas you take and the price of one, find how many were
free and how much you pay.

Input: two integers N and P: samosas taken (1 <= N <= 1000) and price of one (1 <= P <= 100).

Output: two lines: the number of free samosas, then the amount to pay.

Example: for input "10 15", 2 samosas are free, you pay for 8, so print 2 then 120.
""", r"""
#include <stdio.h>

int main(void) {
    int n, p;
    scanf("%d %d", &n, &p);
    int free = n / 4;
    printf("%d\n%d\n", free, (n - free) * p);
    return 0;
}
""", m_samosa, ["10 15\n", "3 20\n", "4 10\n", "1 1\n", "1000 100\n", "7 12\n", "8 5\n"]),

    q("c-leap", "Leap Year Detective", "Conditionals", "easy", """
Is the year a leap year? A year is a leap year if it is divisible by 400,
or divisible by 4 but not by 100.

Input: one year Y (1 <= Y <= 9999).

Output: YES if Y is a leap year, otherwise NO.

Examples: 2024 is YES, 1900 is NO, 2000 is YES.
""", r"""
#include <stdio.h>

int main(void) {
    int y;
    scanf("%d", &y);
    if (y % 400 == 0 || (y % 4 == 0 && y % 100 != 0))
        printf("YES\n");
    else
        printf("NO\n");
    return 0;
}
""", m_leap, ["2024\n", "1900\n", "2000\n", "2023\n", "2100\n", "2400\n", "4\n", "1\n"]),

    q("c-grade", "Report Card", "Conditionals", "easy", """
Turn marks out of 100 into a grade:

90 to 100: A
75 to 89: B
60 to 74: C
40 to 59: D
0 to 39: F

Marks below 0 or above 100 are a typo: print INVALID.

Input: one integer M (-1000 <= M <= 1000).

Output: the grade letter, or INVALID.
""", r"""
#include <stdio.h>

int main(void) {
    int m;
    scanf("%d", &m);
    if (m < 0 || m > 100) printf("INVALID\n");
    else if (m >= 90) printf("A\n");
    else if (m >= 75) printf("B\n");
    else if (m >= 60) printf("C\n");
    else if (m >= 40) printf("D\n");
    else printf("F\n");
    return 0;
}
""", m_grade, ["93\n", "-5\n", "90\n", "89\n", "75\n", "74\n", "60\n", "40\n", "39\n", "0\n", "100\n", "101\n"]),

    q("c-digits", "Digit Sum", "Loops", "easy", """
Add up the digits of a number.

Input: one integer N (0 <= N <= 1000000000).

Output: the sum of the digits of N.

Example: 4096 gives 4 + 0 + 9 + 6 = 19.

Hint: N % 10 is the last digit and N / 10 removes it.
""", r"""
#include <stdio.h>

int main(void) {
    int n, sum = 0;
    scanf("%d", &n);
    while (n > 0) {
        sum += n % 10;
        n /= 10;
    }
    printf("%d\n", sum);
    return 0;
}
""", m_digits, ["4096\n", "7\n", "0\n", "1000000000\n", "999999999\n", "10\n", "123456789\n"]),

    q("c-chai-samosa", "Chai Samosa", "Loops", "easy", """
Count from 1 to N, one number per line, but:

- for multiples of 3 print Chai,
- for multiples of 5 print Samosa,
- for multiples of both 3 and 5 print ChaiSamosa.

Input: one integer N (1 <= N <= 100).

Output: N lines as described.

Example for N = 5: 1, 2, Chai, 4, Samosa.
""", r"""
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    for (int i = 1; i <= n; i++) {
        if (i % 15 == 0) printf("ChaiSamosa\n");
        else if (i % 3 == 0) printf("Chai\n");
        else if (i % 5 == 0) printf("Samosa\n");
        else printf("%d\n", i);
    }
    return 0;
}
""", m_chai, ["5\n", "15\n", "1\n", "3\n", "30\n", "100\n"]),

    q("c-stairs", "Number Staircase", "Patterns", "easy", """
Print a staircase of numbers with N rows. Row i holds the numbers 1 to i,
separated by single spaces.

Input: one integer N (1 <= N <= 20).

Output: N rows. For N = 4:

1
1 2
1 2 3
1 2 3 4
""", r"""
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= i; j++)
            printf(j < i ? "%d " : "%d\n", j);
    }
    return 0;
}
""", m_stairs, ["4\n", "1\n", "2\n", "9\n", "12\n", "20\n"]),

    q("c-top-score", "Top Score", "Arrays", "medium", """
The quiz is over. Find the highest score and how many students got it.

Input: the first line has N (1 <= N <= 1000), the number of students.
The second line has N scores, each between 0 and 100.

Output: the highest score and how many students scored it, separated by a space.

Example: scores 45 78 92 60 92 give "92 2".
""", r"""
#include <stdio.h>

int main(void) {
    int n, a[1000];
    scanf("%d", &n);
    for (int i = 0; i < n; i++) scanf("%d", &a[i]);
    int best = a[0], count = 0;
    for (int i = 1; i < n; i++)
        if (a[i] > best) best = a[i];
    for (int i = 0; i < n; i++)
        if (a[i] == best) count++;
    printf("%d %d\n", best, count);
    return 0;
}
""", m_top, ["5\n45 78 92 60 92\n", "1\n0\n", "4\n100 99 100 100\n", "6\n7 7 7 7 7 7\n", "3\n0 0 1\n",
             "8\n12 85 33 85 9 60 85 1\n", lines(1000, " ".join(str((i * 37) % 101) for i in range(1000)))]),

    q("c-reverse", "Backwards Queue", "Arrays", "medium", """
The queue has to leave the hall in reverse order. Print the roll numbers
from last to first.

Input: the first line has N (1 <= N <= 1000). The second line has N roll
numbers (each between 1 and 100000).

Output: the N roll numbers in reverse order, on one line, separated by spaces.

Example: N = 5 and 11 22 33 44 55 prints 55 44 33 22 11.
""", r"""
#include <stdio.h>

int main(void) {
    int n, a[1000];
    scanf("%d", &n);
    for (int i = 0; i < n; i++) scanf("%d", &a[i]);
    for (int i = n - 1; i >= 0; i--)
        printf(i > 0 ? "%d " : "%d\n", a[i]);
    return 0;
}
""", m_reverse, ["5\n11 22 33 44 55\n", "1\n42\n", "2\n1 2\n", "6\n3 1 4 1 5 9\n",
                 lines(1000, " ".join(str(i * 7 % 100000 + 1) for i in range(1000)))]),

    q("c-palindrome", "Palindrome Checker", "Strings", "medium", """
A palindrome reads the same forwards and backwards, like level or racecar.

Input: one word of lowercase letters (1 to 100 characters).

Output: YES if the word is a palindrome, otherwise NO.

Hint: strlen from <string.h> gives the length.
""", r"""
#include <stdio.h>
#include <string.h>

int main(void) {
    char w[128];
    scanf("%127s", w);
    int n = strlen(w), ok = 1;
    for (int i = 0; i < n / 2; i++)
        if (w[i] != w[n - 1 - i]) ok = 0;
    printf(ok ? "YES\n" : "NO\n");
    return 0;
}
""", m_palin, ["level\n", "coding\n", "a\n", "abba\n", "ab\n", "racecar\n", "abcdba\n", "malayalam\n",
               "x" * 100 + "\n"]),

    q("c-vowels", "Vowel Counter", "Strings", "medium", """
Count the vowels (a, e, i, o, u, in upper or lower case) in a sentence.

Input: one line of text, at most 200 characters. It may contain spaces and punctuation.

Output: the number of vowels.

Example: Hello World has 3 vowels.

Hint: read the whole line with fgets, since scanf("%s") stops at the first space.
""", r"""
#include <stdio.h>
#include <ctype.h>

int main(void) {
    char line[256];
    int count = 0;
    if (fgets(line, sizeof line, stdin)) {
        for (int i = 0; line[i]; i++) {
            char c = tolower((unsigned char)line[i]);
            if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') count++;
        }
    }
    printf("%d\n", count);
    return 0;
}
""", m_vowels, ["Hello World\n", "Rhythm\n", "AEIOU aeiou\n", "Welcome to IIIT Surat, coders!\n",
                "C programming is FUN.\n", "xyz 123 !?\n"]),

    q("c-prime", "Prime Time", "Functions", "medium", """
Complete the function is_prime(n): it returns 1 if n is prime and 0
otherwise. main is already written: it reads T numbers and prints PRIME
or NOT PRIME for each.

A prime has exactly two divisors, 1 and itself, so 1 is not prime.

Input: T (1 <= T <= 20), then T integers, each 1 <= n <= 1000000.

Output: one line per number: PRIME or NOT PRIME.
""", r"""
#include <stdio.h>

int is_prime(int n) {
    if (n < 2) return 0;
    for (int i = 2; i * i <= n; i++)
        if (n % i == 0) return 0;
    return 1;
}

int main(void) {
    int t, n;
    scanf("%d", &t);
    while (t--) {
        scanf("%d", &n);
        printf(is_prime(n) ? "PRIME\n" : "NOT PRIME\n");
    }
    return 0;
}
""", m_prime, ["3\n7\n10\n13\n", "1\n1\n", "4\n2\n3\n4\n9\n", "3\n999983\n1000000\n25\n",
               "5\n97\n91\n49\n17\n121\n", "2\n999981\n524287\n"], starter=r"""#include <stdio.h>

// Return 1 if n is prime, 0 otherwise.
int is_prime(int n) {

    return 0;
}

int main(void) {
    int t, n;
    scanf("%d", &t);
    while (t--) {
        scanf("%d", &n);
        printf(is_prime(n) ? "PRIME\n" : "NOT PRIME\n");
    }
    return 0;
}
"""),
]

SETS = {
    "c-fundamentals": {
        "title": "C fundamentals", "language": "c",
        "about": "Beginner C: input and output, operators, conditionals, loops, patterns, arrays, strings and functions.",
        "questions": C_FUNDAMENTALS,
    },
}


def latex_table(sid: str, s: dict) -> str:
    rows = "\n".join(
        f"    {x['title']} & {x['topic']} & {x['level']} & {sum(not t['hidden'] for t in x['tests'])} & "
        f"{sum(t['hidden'] for t in x['tests'])} \\\\" for x in s["questions"])
    return f"""% Generated by backend/scripts/build_question_sets.py. Do not edit by hand.
\\begin{{table}}[ht]
  \\centering\\small
  \\caption{{The original {s['title']} set: each question's reference solution passes all its tests and its starter code does not (\\texttt{{tests/test\\_question\\_sets.py}}).}}
  \\label{{tab:set-{sid}}}
  \\begin{{tabular}}{{@{{}}lllrr@{{}}}}
    \\toprule
    Question & Topic & Level & Visible & Hidden \\\\
    \\midrule
{rows}
    \\bottomrule
  \\end{{tabular}}
\\end{{table}}
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for sid, s in SETS.items():
        refs = [x["ref"] for x in s["questions"]]
        assert len(refs) == len(set(refs)), f"duplicate refs in {sid}"
        (OUT / f"{sid}.json").write_text(json.dumps({"id": sid} | s, indent=1, ensure_ascii=False) + "\n")
        (TABLES / f"question-set-{sid}.tex").write_text(latex_table(sid, s))
        print(f"{sid}: {len(refs)} questions, {sum(len(x['tests']) for x in s['questions'])} tests")


if __name__ == "__main__":
    main()
