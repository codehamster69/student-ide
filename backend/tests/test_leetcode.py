"""LeetCode questions from LeetCodeDataset: bundled tests and topics, the
harness (linked lists, trees, any-order answers) and the rule that LeetCode's
problem text is never stored, only pointed at for the browser to load."""

import gzip
import json

import pytest
from fastapi.testclient import TestClient

from studentide import grading
from studentide.app import create_app
from studentide.providers.leetcode import DATA, LeetCode, topics

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}

# Our own solutions (not the dataset's), written the way a student would on LeetCode.
SOLUTIONS = {
    "two-sum": """
class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        seen = {}
        for i, x in enumerate(nums):
            if target - x in seen:
                return [i, seen[target - x]]  # reversed order on purpose: any order is accepted
            seen[x] = i
""",
    "add-two-numbers": """
class Solution:
    def addTwoNumbers(self, l1: Optional[ListNode], l2: Optional[ListNode]) -> Optional[ListNode]:
        dummy = tail = ListNode()
        carry = 0
        while l1 or l2 or carry:
            s = carry + (l1.val if l1 else 0) + (l2.val if l2 else 0)
            carry, d = divmod(s, 10)
            tail.next = ListNode(d)
            tail = tail.next
            l1, l2 = l1 and l1.next, l2 and l2.next
        return dummy.next
""",
    "binary-tree-inorder-traversal": """
class Solution:
    def inorderTraversal(self, root: Optional[TreeNode]) -> List[int]:
        return self.inorderTraversal(root.left) + [root.val] + self.inorderTraversal(root.right) if root else []
""",
    "invert-binary-tree": """
class Solution:
    def invertTree(self, root: Optional[TreeNode]) -> Optional[TreeNode]:
        if root:
            root.left, root.right = self.invertTree(root.right), self.invertTree(root.left)
        return root
""",
    "median-of-two-sorted-arrays": """
class Solution:
    def findMedianSortedArrays(self, nums1: List[int], nums2: List[int]) -> float:
        a = sorted(nums1 + nums2)
        n = len(a)
        return a[n // 2] / 1 if n % 2 else (a[n // 2 - 1] + a[n // 2]) / 2
""",
    "subsets": """
class Solution:
    def subsets(self, nums: List[int]) -> List[List[int]]:
        out = [[]]
        for x in reversed(nums):
            out += [[x] + s for s in out]
        return out
""",
}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "t.sqlite3", admin_token=TOKEN, serve_frontend=False))


def rows():
    with gzip.open(DATA, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_bundle_has_tests_and_topics_but_no_problem_text():
    rs = rows()
    assert len(rs) > 2800
    assert all(len(r["tests"]) >= 3 for r in rs)
    assert sum(bool(topics(r)) for r in rs) / len(rs) > 0.95
    # LeetCode's own text never ships: no description field, and no sentence of the Two Sum statement
    assert all("problem_description" not in r and "description" not in r for r in rs)
    raw = gzip.decompress(DATA.read_bytes()).decode()
    assert "indices of the two numbers" not in raw and "Example 1" not in raw


@pytest.mark.parametrize("ref", sorted(SOLUTIONS))
def test_our_solutions_pass_every_test(ref):
    q = LeetCode().fetch("python", ref)
    code = q.starter_code.split("class Solution")[0] + SOLUTIONS[ref]
    g = grading.grade(q.as_dict(), code)
    assert g["passed"] == g["total"] >= 3, [r for r in g["results"] if not r["passed"]][:2]


def test_wrong_answers_fail():
    q = LeetCode().fetch("python", "two-sum").as_dict()
    g = grading.grade(q, "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 0]\n")
    assert g["passed"] < g["total"]
    q = LeetCode().fetch("python", "invert-binary-tree").as_dict()
    g = grading.grade(q, "class Solution:\n    def invertTree(self, root):\n        return root\n")
    assert g["passed"] < g["total"]


def test_starter_code_runs_as_given():
    q = LeetCode().fetch("python", "add-two-numbers")
    assert "class ListNode" in q.starter_code and "from typing import *" in q.starter_code
    assert "# class ListNode" not in q.starter_code and q.starter_code.rstrip().endswith("pass")
    compile(q.starter_code, "starter", "exec")


def test_browse_by_topic_and_import_without_text(client):
    cats = client.get("/api/teach/sources/leetcode/categories?language=python", headers=ADMIN).json()
    ids = {c["id"] for c in cats}
    assert {"topic:dp", "topic:graphs", "topic:linked-lists", "topic:trees", "topic:sliding-window", "level:easy"} <= ids
    trees = client.get("/api/teach/sources/leetcode/questions?language=python&category=topic:trees", headers=ADMIN).json()
    assert trees and trees[0]["difficulty"] == "easy"
    c_cats = client.get("/api/teach/sources/leetcode/categories?language=c", headers=ADMIN)
    assert c_cats.status_code == 200 and {"topic:trees", "level:hard"} <= {c["id"] for c in c_cats.json()}
    assert client.get("/api/teach/sources/leetcode/categories?language=rust", headers=ADMIN).status_code in (400, 422)

    lab = client.post("/api/teach/labs", json={"title": "L", "language": "python"}, headers=ADMIN).json()
    lab = client.post(f"/api/teach/labs/{lab['id']}/import", json={"provider": "leetcode", "ref": "two-sum"}, headers=ADMIN).json()
    q = next(q for q in lab["questions"] if q["id"] == lab["imported"])
    assert q["title"] == "1. Two Sum" and q["prompt"] == ""
    assert q["source"]["url"] == "https://leetcode.com/problems/two-sum/"
    live = q["source"]["live_prompt"]
    assert live["url"].startswith("https://datasets-server.huggingface.co/rows?") and live["match"] == {"task_id": "two-sum"}
    assert any(t["hidden"] for t in q["tests"]) and not q["tests"][0]["hidden"]
    code = q["starter_code"].split("class Solution")[0] + SOLUTIONS["two-sum"]
    g = client.post(f"/api/teach/questions/{q['id']}/check", json={"code": code}, headers=ADMIN).json()
    assert g["passed"] == g["total"]
    # a teacher may write their own prompt instead of the live text
    r = client.patch(f"/api/teach/questions/{q['id']}", json={"prompt": "Find two numbers that add up to the target."},
                     headers=ADMIN).json()
    assert next(x for x in r["questions"] if x["id"] == q["id"])["prompt"].startswith("Find two")


def test_json_compare_allows_float_rounding():
    assert grading.outputs_match("0.30000000000000004", "0.3", "json")
    assert grading.outputs_match("[1, 2.5000001]", "[1, 2.5]", "json")
    assert not grading.outputs_match("[1, 2.6]", "[1, 2.5]", "json")
    assert not grading.outputs_match("true", "1.0", "json")


def test_server_fallback_for_the_text(client):
    calls = []
    row = {"rows": [{"row": {"task_id": "two-sum", "problem_description": "  Text from the dataset.  "}}]}

    def fake(url):
        calls.append(url)
        return json.dumps(row).encode()

    from studentide.providers import PROVIDERS
    PROVIDERS["leetcode"].get, saved = fake, PROVIDERS["leetcode"].get
    try:
        PROVIDERS["leetcode"]._texts.clear()
        r = client.get("/api/live-prompt/leetcode/two-sum").json()
        assert r == {"text": "Text from the dataset."}
        client.get("/api/live-prompt/leetcode/two-sum")
        assert len(calls) == 1 and "offset=" in calls[0]  # cached in memory
        assert client.get("/api/live-prompt/leetcode/add-two-numbers").status_code == 502  # row is not that problem
        assert client.get("/api/live-prompt/leetcode/nope").status_code == 404
        assert client.get("/api/live-prompt/mbpp/1").status_code == 404
    finally:
        PROVIDERS["leetcode"].get = saved
        PROVIDERS["leetcode"]._texts.clear()
