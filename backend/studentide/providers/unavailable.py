"""Platforms with no permitted way to fetch questions automatically.

(CodeChef and Codeforces problems are browsable through the CodeContests
dataset instead, see codecontests.py, and LeetCode problems through
LeetCodeDataset, see leetcode.py; their own sites still cannot be fetched.)

None of LeetCode, HackerRank and CodeChef publishes an API for reading problem statements or test
data, and none licenses its problems for reuse in another product. LeetCode's
GraphQL endpoint is internal and undocumented; HackerRank's API covers only a
company's own tests and its terms forbid copying any part of the service;
CodeChef shut its public API in 2020 and puts pages behind captchas. Scraping
any of them would mean working around that, so instead a teacher keeps a link
to the original and writes the question themselves. See docs/question-sources.md.
"""

from __future__ import annotations

from .base import Provider


class HackerRank(Provider):
    id = "hackerrank"
    name = "HackerRank"
    status = "link_only"
    about = ("Its API only covers a company's own tests, and its terms forbid copying the site's content. "
             "Link a challenge and write the question in your own words.")
    terms_url = "https://www.hackerrank.com/terms-of-service"
    hosts = ("hackerrank.com",)
