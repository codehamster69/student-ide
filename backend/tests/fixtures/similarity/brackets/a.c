#include <stdio.h>
#include <string.h>

int main(void) {
    char s[100005], stack[100005];
    scanf("%100000s", s);
    int top = 0, ok = 1;
    for (int i = 0; s[i] && ok; i++) {
        char c = s[i];
        if (c == '(' || c == '[' || c == '{') {
            stack[top++] = c;
        } else {
            if (top == 0) { ok = 0; break; }
            char open = stack[--top];
            if ((c == ')' && open != '(') || (c == ']' && open != '[') || (c == '}' && open != '{'))
                ok = 0;
        }
    }
    printf("%s\n", ok && top == 0 ? "YES" : "NO");
    return 0;
}
