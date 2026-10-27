s = input().strip()
stack = []
pairs = {")": "(", "]": "[", "}": "{"}
ok = True
for c in s:
    if c in "([{":
        stack.append(c)
    elif not stack or stack.pop() != pairs[c]:
        ok = False
        break
print("YES" if ok and not stack else "NO")
