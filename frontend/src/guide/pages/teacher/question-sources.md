---
title: Question sources
summary: Where questions can come from: your own, the bundled C set, Codeforces, CodeChef, LeetCode, MBPP, Exercism, and link-only sites.
order: 3
keywords: [questions, import, leetcode, codeforces, codechef, mbpp, exercism, hackerrank, dataset, tests, topics, difficulty, licence]
---

In a lab's question editor choose **Import** to pick a question by topic and difficulty. The pick is copied into your lab as an ordinary question, with its source, link and licence kept as attribution, so you can edit it freely.

| Source | How | Notes |
| --- | --- | --- |
| **Student IDE sets** | Bundled, original | 13 C fundamentals questions, each with visible examples and hidden tests |
| **Codeforces** | Bundled dataset + link | Thousands of problems by topic and rating, with tests |
| **CodeChef** | Bundled dataset + link | Easy and medium problems, difficulty only |
| **LeetCode** | Bundled tests, text fetched live | Topics and Easy/Medium/Hard. The statement is fetched on demand and never stored; if it cannot be fetched, students see a link and the lab editor warns you |
| **MBPP** | Live | Beginner problems, topics guessed from wording |
| **Exercism** | Live | Python and JavaScript have tests; C, C++ and Java exercises import without tests |
| **HackerRank** | Link only | Paste a link and write the question in your own words |

## Tests and languages

Imported questions keep their tests. LeetCode and MBPP questions work in **every lab language** with the same tests, so a problem is the same problem whether students use C, C++, Java, JavaScript or Python. A few questions that return mixed types stay Python only; the picker explains unsupported cases.

Hidden tests give students only pass or fail. For problems with several right answers, a checker judges the output.

## Advice

- For competitions and exams, writing the prompt yourself is the safest choice when a source's text might be seen in advance.
- Always run a question yourself (View as student) before class.
- Competition questions must have at least one test.

Sandbox Labs can import the same questions as assignments; see [Sandbox Labs](sandbox-labs).
