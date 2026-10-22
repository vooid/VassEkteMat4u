// Prints the first N Fibonacci numbers, where N is read from the command line or stdin.
#include <cstdint>
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    long long steps = -1;
    try {
        if (argc > 1) {
            steps = std::stoll(argv[1]);
        } else {
            std::cout << "Number of steps: ";
            std::string line;
            std::getline(std::cin, line);
            steps = std::stoll(line);
        }
    } catch (const std::exception&) {
        std::cerr << "Please enter a whole number.\n";
        return 1;
    }

    // F(93) is the largest Fibonacci number that fits in an unsigned 64-bit integer.
    if (steps < 0 || steps > 94) {
        std::cerr << "Steps must be between 0 and 94.\n";
        return 1;
    }

    std::uint64_t a = 0, b = 1;
    for (long long i = 0; i < steps; ++i) {
        std::cout << "F(" << i << ") = " << a << '\n';
        std::uint64_t next = a + b;
        a = b;
        b = next;
    }
    return 0;
}
