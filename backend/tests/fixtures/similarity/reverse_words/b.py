line = input()
words = []
current = ""
for ch in line:
    if ch == " ":
        if current:
            words.append(current)
            current = ""
    else:
        current += ch
if current:
    words.append(current)
out = []
i = len(words) - 1
while i >= 0:
    out.append(words[i])
    i -= 1
print(" ".join(out))
