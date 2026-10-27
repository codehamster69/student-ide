import sys
from collections import deque

stack = deque()
for word in sys.stdin.readline().split():
    stack.appendleft(word)
result = ""
for idx, word in enumerate(stack):
    if idx:
        result += " "
    result += word
print(result)
