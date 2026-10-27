#include <iostream>
#include <sstream>
#include <vector>
#include <algorithm>
using namespace std;

int main() {
    string line, w;
    getline(cin, line);
    istringstream in(line);
    vector<string> parts;
    while (in >> w) parts.push_back(w);
    reverse(parts.begin(), parts.end());
    for (size_t i = 0; i < parts.size(); i++) cout << (i ? " " : "") << parts[i];
    cout << '\n';
    return 0;
}
