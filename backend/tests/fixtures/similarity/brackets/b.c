#include <stdio.h>

static char match_of(char closing) {
    switch (closing) {
        case ')': return '(';
        case ']': return '[';
        case '}': return '{';
        default: return 0;
    }
}

int main() {
    static char line[100005];
    static char pending[100005];
    int depth = 0;
    if (!fgets(line, sizeof line, stdin)) return 0;
    for (char *p = line; *p && *p != '\n'; ++p) {
        char m = match_of(*p);
        if (!m) {
            pending[depth] = *p;
            depth++;
        } else if (depth > 0 && pending[depth - 1] == m) {
            depth--;
        } else {
            puts("NO");
            return 0;
        }
    }
    puts(depth ? "NO" : "YES");
    return 0;
}
