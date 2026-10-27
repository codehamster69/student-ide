"""LeetCode (and MBPP) questions in C, C++, Java and JavaScript: starters and
harnesses generated from the Python signature (providers/polyglot.py), the
same tests in every language, checked with our own solutions through the
real grader. scripts/check_polyglot.py checks every type and signature shape."""

import shutil

import pytest

from studentide import grading
from studentide.providers import leetcode, polyglot
from studentide.providers.leetcode import LeetCode

TOOLS = {"c": "gcc", "cpp": "g++", "java": "javac", "javascript": "node"}

# Our own solutions, written as a student would on LeetCode in each language.
SOLUTIONS = {
    "c": {
        "two-sum": """
int* twoSum(int* nums, int numsSize, int target, int* returnSize) {
    int* out = malloc(2 * sizeof(int));
    *returnSize = 2;
    for (int i = 0; i < numsSize; i++)
        for (int j = 0; j < i; j++)
            if (nums[i] + nums[j] == target) { out[0] = i; out[1] = j; return out; }
    *returnSize = 0;
    return out;
}
""",
        "add-two-numbers": """
struct ListNode* addTwoNumbers(struct ListNode* l1, struct ListNode* l2) {
    struct ListNode dummy = {0, NULL}, *tail = &dummy;
    int carry = 0;
    while (l1 || l2 || carry) {
        int s = carry + (l1 ? l1->val : 0) + (l2 ? l2->val : 0);
        tail->next = calloc(1, sizeof(struct ListNode));
        tail = tail->next;
        tail->val = s % 10;
        carry = s / 10;
        if (l1) l1 = l1->next;
        if (l2) l2 = l2->next;
    }
    return dummy.next;
}
""",
        "invert-binary-tree": """
struct TreeNode* invertTree(struct TreeNode* root) {
    if (!root) return NULL;
    struct TreeNode* left = root->left;
    root->left = invertTree(root->right);
    root->right = invertTree(left);
    return root;
}
""",
        "median-of-two-sorted-arrays": """
double findMedianSortedArrays(int* nums1, int nums1Size, int* nums2, int nums2Size) {
    int n = nums1Size + nums2Size, i = 0, j = 0, prev = 0, cur = 0;
    for (int k = 0; k <= n / 2; k++) {
        prev = cur;
        cur = (j >= nums2Size || (i < nums1Size && nums1[i] <= nums2[j])) ? nums1[i++] : nums2[j++];
    }
    return n % 2 ? cur : (prev + cur) / 2.0;
}
""",
        "group-anagrams": """
static int cmp_char(const void* a, const void* b) { return *(const char*) a - *(const char*) b; }

char*** groupAnagrams(char** strs, int strsSize, int* returnSize, int** returnColumnSizes) {
    char** keys = malloc(strsSize * sizeof(char*));
    char*** groups = malloc(strsSize * sizeof(char**));
    *returnColumnSizes = calloc(strsSize, sizeof(int));
    *returnSize = 0;
    for (int i = 0; i < strsSize; i++) {
        char* key = malloc(strlen(strs[i]) + 1);
        strcpy(key, strs[i]);
        qsort(key, strlen(key), 1, cmp_char);
        int g = 0;
        while (g < *returnSize && strcmp(keys[g], key)) g++;
        if (g == *returnSize) { keys[g] = key; groups[g] = malloc(strsSize * sizeof(char*)); (*returnSize)++; }
        groups[g][(*returnColumnSizes)[g]++] = strs[i];
    }
    return groups;
}
""",
        "valid-parentheses": """
bool isValid(char* s) {
    int n = strlen(s), top = 0;
    char* stack = malloc(n + 1);
    for (int i = 0; i < n; i++) {
        char c = s[i];
        if (c == '(' || c == '[' || c == '{') stack[top++] = c;
        else if (!top || stack[--top] != (c == ')' ? '(' : c == ']' ? '[' : '{')) return false;
    }
    return top == 0;
}
""",
    },
    "cpp": {
        "two-sum": """
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int, int> seen;
        for (int i = 0; i < (int) nums.size(); i++) {
            if (seen.count(target - nums[i])) return {i, seen[target - nums[i]]};
            seen[nums[i]] = i;
        }
        return {};
    }
""",
        "add-two-numbers": """
    ListNode* addTwoNumbers(ListNode* l1, ListNode* l2) {
        ListNode dummy, *tail = &dummy;
        int carry = 0;
        while (l1 || l2 || carry) {
            int s = carry + (l1 ? l1->val : 0) + (l2 ? l2->val : 0);
            tail = tail->next = new ListNode(s % 10);
            carry = s / 10;
            l1 = l1 ? l1->next : nullptr;
            l2 = l2 ? l2->next : nullptr;
        }
        return dummy.next;
    }
""",
        "invert-binary-tree": """
    TreeNode* invertTree(TreeNode* root) {
        if (root) swap(root->left, root->right), invertTree(root->left), invertTree(root->right);
        return root;
    }
""",
        "median-of-two-sorted-arrays": """
    double findMedianSortedArrays(vector<int>& nums1, vector<int>& nums2) {
        vector<int> a(nums1);
        a.insert(a.end(), nums2.begin(), nums2.end());
        sort(a.begin(), a.end());
        int n = a.size();
        return n % 2 ? a[n / 2] : (a[n / 2 - 1] + a[n / 2]) / 2.0;
    }
""",
        "group-anagrams": """
    vector<vector<string>> groupAnagrams(vector<string>& strs) {
        map<string, vector<string>> groups;
        for (auto& s : strs) { string k = s; sort(k.begin(), k.end()); groups[k].push_back(s); }
        vector<vector<string>> out;
        for (auto& [k, g] : groups) out.push_back(g);
        return out;
    }
""",
        "valid-parentheses": """
    bool isValid(string s) {
        string st;
        for (char c : s) {
            if (c == '(' || c == '[' || c == '{') st += c;
            else if (st.empty() || st.back() != (c == ')' ? '(' : c == ']' ? '[' : '{')) return false;
            else st.pop_back();
        }
        return st.empty();
    }
""",
    },
    "java": {
        "two-sum": """
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> seen = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            if (seen.containsKey(target - nums[i])) return new int[] {i, seen.get(target - nums[i])};
            seen.put(nums[i], i);
        }
        return new int[0];
    }
""",
        "add-two-numbers": """
    public ListNode addTwoNumbers(ListNode l1, ListNode l2) {
        ListNode dummy = new ListNode(), tail = dummy;
        int carry = 0;
        while (l1 != null || l2 != null || carry > 0) {
            int s = carry + (l1 != null ? l1.val : 0) + (l2 != null ? l2.val : 0);
            tail = tail.next = new ListNode(s % 10);
            carry = s / 10;
            l1 = l1 != null ? l1.next : null;
            l2 = l2 != null ? l2.next : null;
        }
        return dummy.next;
    }
""",
        "invert-binary-tree": """
    public TreeNode invertTree(TreeNode root) {
        if (root == null) return null;
        TreeNode left = root.left;
        root.left = invertTree(root.right);
        root.right = invertTree(left);
        return root;
    }
""",
        "median-of-two-sorted-arrays": """
    public double findMedianSortedArrays(int[] nums1, int[] nums2) {
        int[] a = new int[nums1.length + nums2.length];
        System.arraycopy(nums1, 0, a, 0, nums1.length);
        System.arraycopy(nums2, 0, a, nums1.length, nums2.length);
        Arrays.sort(a);
        int n = a.length;
        return n % 2 == 1 ? a[n / 2] : (a[n / 2 - 1] + a[n / 2]) / 2.0;
    }
""",
        "group-anagrams": """
    public List<List<String>> groupAnagrams(String[] strs) {
        Map<String, List<String>> groups = new HashMap<>();
        for (String s : strs) {
            char[] k = s.toCharArray();
            Arrays.sort(k);
            groups.computeIfAbsent(new String(k), x -> new ArrayList<>()).add(s);
        }
        return new ArrayList<>(groups.values());
    }
""",
        "valid-parentheses": """
    public boolean isValid(String s) {
        Deque<Character> st = new ArrayDeque<>();
        for (char c : s.toCharArray()) {
            if ("([{".indexOf(c) >= 0) st.push(c);
            else if (st.isEmpty() || st.pop() != (c == ')' ? '(' : c == ']' ? '[' : '{')) return false;
        }
        return st.isEmpty();
    }
""",
    },
    "javascript": {
        "two-sum": """
var twoSum = function(nums, target) {
    const seen = new Map();
    for (let i = 0; i < nums.length; i++) {
        if (seen.has(target - nums[i])) return [i, seen.get(target - nums[i])];
        seen.set(nums[i], i);
    }
};
""",
        "add-two-numbers": """
var addTwoNumbers = function(l1, l2) {
    const dummy = new ListNode();
    let tail = dummy, carry = 0;
    while (l1 || l2 || carry) {
        const s = carry + (l1 ? l1.val : 0) + (l2 ? l2.val : 0);
        tail = tail.next = new ListNode(s % 10);
        carry = Math.floor(s / 10);
        l1 = l1 && l1.next;
        l2 = l2 && l2.next;
    }
    return dummy.next;
};
""",
        "invert-binary-tree": """
var invertTree = function(root) {
    if (root) [root.left, root.right] = [invertTree(root.right), invertTree(root.left)];
    return root;
};
""",
        "median-of-two-sorted-arrays": """
var findMedianSortedArrays = function(nums1, nums2) {
    const a = [...nums1, ...nums2].sort((x, y) => x - y), n = a.length;
    return n % 2 ? a[(n - 1) / 2] : (a[n / 2 - 1] + a[n / 2]) / 2;
};
""",
        "group-anagrams": """
var groupAnagrams = function(strs) {
    const groups = new Map();
    for (const s of strs) {
        const k = [...s].sort().join("");
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k).push(s);
    }
    return [...groups.values()];
};
""",
        "valid-parentheses": """
var isValid = function(s) {
    const st = [], open = { ")": "(", "]": "[", "}": "{" };
    for (const c of s) {
        if ("([{".includes(c)) st.push(c);
        else if (st.pop() !== open[c]) return false;
    }
    return st.length === 0;
};
""",
    },
}


def with_solution(starter: str, solution: str, language: str) -> str:
    """The starter with its empty function replaced by our solution (as the student would edit it)."""
    if language in ("cpp", "java"):  # the method inside class Solution
        head = starter.split("class Solution")[0]
        return head + "class Solution {\n" + ("public:\n" if language == "cpp" else "") + solution + "}" + (";" if language == "cpp" else "") + "\n"
    # C and JavaScript: everything above the function's doc comment (or its first line)
    head = starter[: starter.rindex("/**")] if "/**" in starter else starter[: starter.rindex("\n", 0, starter.rindex("(")) + 1]
    return head + solution


@pytest.mark.parametrize("language", sorted(SOLUTIONS))
@pytest.mark.parametrize("ref", sorted(SOLUTIONS["c"]))
def test_our_solutions_pass_in_every_language(language, ref):
    if not shutil.which(TOOLS[language]):
        pytest.skip(f"{TOOLS[language]} not installed")
    q = LeetCode().fetch(language, ref)
    code = with_solution(q.starter_code, SOLUTIONS[language][ref], language)
    g = grading.grade(q.as_dict(), code, language)
    assert g["passed"] == g["total"] >= 3, (code, [r for r in g["results"] if not r["passed"]][:2])


@pytest.mark.parametrize("language", sorted(SOLUTIONS))
def test_wrong_answers_fail_in_every_language(language):
    if not shutil.which(TOOLS[language]):
        pytest.skip(f"{TOOLS[language]} not installed")
    q = LeetCode().fetch(language, "invert-binary-tree")
    wrong = {"c": "struct TreeNode* invertTree(struct TreeNode* root) { return root; }\n",
             "cpp": "    TreeNode* invertTree(TreeNode* root) { return root; }\n",
             "java": "    public TreeNode invertTree(TreeNode root) { return root; }\n",
             "javascript": "var invertTree = function(root) { return root; };\n"}[language]
    g = grading.grade(q.as_dict(), with_solution(q.starter_code, wrong, language), language)
    assert 0 < g["passed"] < g["total"]  # a one-node tree is its own mirror; the rest fail


def test_same_tests_in_every_language():
    for ref in ("two-sum", "add-two-numbers", "group-anagrams", "merge-intervals"):
        tests = {lang: [(t["stdin"], t["expected"]) for t in LeetCode().fetch(lang, ref).tests]
                 for lang in ("python", *polyglot.LANGUAGES)}
        assert len({tuple(t) for t in tests.values()}) == 1, ref
        assert tests["c"][0][0].count("\n") == len(leetcode._typed("c")[ref][0].params)  # one JSON line per argument


def test_starters_look_like_leetcode():
    p = LeetCode()
    assert "int* twoSum(int* nums, int numsSize, int target, int* returnSize) {" in p.fetch("c", "two-sum").starter_code
    assert "vector<int> twoSum(vector<int>& nums, int target) {" in p.fetch("cpp", "two-sum").starter_code
    assert "public int[] twoSum(int[] nums, int target) {" in p.fetch("java", "two-sum").starter_code
    assert "var twoSum = function(nums, target) {" in p.fetch("javascript", "two-sum").starter_code
    assert "struct ListNode {" in p.fetch("c", "add-two-numbers").starter_code
    assert "char nextGreatestLetter(vector<char>& letters, char target)" in \
        p.fetch("cpp", "find-smallest-letter-greater-than-target").starter_code
    assert "long long" in p.fetch("cpp", "find-the-k-th-character-in-string-game-ii").starter_code


def test_most_problems_work_in_every_language():
    n = len(leetcode._load())
    for lang in polyglot.LANGUAGES:
        assert len(leetcode._typed(lang)) / n > 0.99, lang


def test_types_from_hints_and_values():
    import ast
    hint = lambda s: polyglot.from_hint(ast.parse(s, mode="eval").body)  # noqa: E731
    assert hint("List[List[int]]") == "int[][]" and hint("Optional[TreeNode]") == "TreeNode"
    assert hint("Dict[str, int]") is None and hint("List[List[List[int]]]") is None
    assert polyglot.narrow("int[]", [[1, 2**40]]) == "long[]"
    assert polyglot.narrow("string", ["a", "b"]) == "char"
    assert polyglot.guess([(1, 2), [3]]) == "int[]" and polyglot.guess([1, 2.5]) == "double"
    assert polyglot.guess([[1, "a"]]) is None  # a mixed tuple has no single type
    assert not polyglot.in_range([2**60], "javascript") and polyglot.in_range([2**60], "java")


MBPP_ROWS = [
    {"task_id": 11, "text": "Write a python function to remove first and last occurrence of a given character from the string.",
     "code": "def remove_Occ(s,ch): \n    return s", "test_list": [
         'assert remove_Occ("hello","l") == "heo"', 'assert remove_Occ("abcda","a") == "bcd"', 'assert remove_Occ("PHP","P") == "H"']},
    {"task_id": 1, "text": "Write a function to sort a list and return it with its length.",
     "code": "def f(xs):\n    return xs", "test_list": [
         "assert f([3, 1]) == ([1, 3], 2)", "assert f([]) == ([], 0)", "assert f([5]) == ([5], 1)"]},
]


def mbpp():
    import json
    from studentide.providers.base import Cached
    from studentide.providers.mbpp import MBPP
    text = "\n".join(json.dumps(r) for r in MBPP_ROWS).encode()
    return MBPP(Cached(lambda url: text))


def test_mbpp_types_come_from_the_tests():
    p = mbpp()
    assert [s.ref for s in p.search("java")] == ["11"]  # the mixed (list, int) answer has no Java type
    assert len(p.search("python")) == 2
    q = p.fetch("c", "11")
    assert "char* remove_Occ(char* s, char ch) {" in q.starter_code and "python" not in q.prompt.lower()
    assert [t["stdin"] for t in q.tests] == [t["stdin"] for t in p.fetch("python", "11").tests]
    with pytest.raises(Exception, match="works in Python"):
        p.fetch("java", "1")


@pytest.mark.parametrize("language,solution", [
    ("python", "def remove_Occ(s, ch):\n    i = s.find(ch)\n    s = s[:i] + s[i + 1:]\n    j = s.rfind(ch)\n    return s[:j] + s[j + 1:]\n"),
    ("c", """
char* remove_Occ(char* s, char ch) {
    int n = strlen(s), first = -1, last = -1, k = 0;
    for (int i = 0; i < n; i++) if (s[i] == ch) { if (first < 0) first = i; last = i; }
    char* out = malloc(n + 1);
    for (int i = 0; i < n; i++) if (i != first && i != last) out[k++] = s[i];
    out[k] = 0;
    return out;
}
"""),
    ("java", """
    public String remove_Occ(String s, char ch) {
        int i = s.indexOf(ch);
        s = s.substring(0, i) + s.substring(i + 1);
        int j = s.lastIndexOf(ch);
        return s.substring(0, j) + s.substring(j + 1);
    }
"""),
])
def test_mbpp_solutions_pass(language, solution):
    if language != "python" and not shutil.which(TOOLS[language]):
        pytest.skip(f"{TOOLS[language]} not installed")
    q = mbpp().fetch(language, "11")
    code = solution if language == "python" else with_solution(q.starter_code, solution, language)
    g = grading.grade(q.as_dict(), code, language)
    assert g["passed"] == g["total"] == 3, [r for r in g["results"] if not r["passed"]]
