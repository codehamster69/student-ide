def balanced(text):
    previous = None
    while previous != text:
        previous = text
        text = text.replace("()", "").replace("[]", "").replace("{}", "")
    return text == ""


print("YES" if balanced(input().strip()) else "NO")
