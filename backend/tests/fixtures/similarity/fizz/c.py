import sys

limit = int(sys.stdin.readline())
lines = []
number = 1
while number <= limit:
    out = ""
    if not number % 3:
        out = out + "Chai"
    if not number % 5:
        out = out + "Samosa"
    lines.append(out if out else str(number))
    number = number + 1
sys.stdout.write("\n".join(lines) + "\n")
