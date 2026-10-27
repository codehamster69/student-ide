#include <iostream>
#include <stack>
#include <string>
#include <map>
using namespace std;

bool balanced(const string& text) {
    map<char, char> pairs = {{')', '('}, {']', '['}, {'}', '{'}};
    stack<char> st;
    for (char ch : text) {
        if (pairs.count(ch)) {
            if (st.empty() || st.top() != pairs[ch]) return false;
            st.pop();
        } else {
            st.push(ch);
        }
    }
    return st.empty();
}

int main() {
    string s;
    cin >> s;
    cout << (balanced(s) ? "YES" : "NO") << endl;
}
