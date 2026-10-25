---
name: cpp-testing
description: Test-driven development and unit testing for modern C++ using GoogleTest, GoogleMock, and CMake CTest. Covers test layout, fixture lifecycle, fakes versus mocks, parameterized tests, test discovery, and sanitizer configurations (ASan, UBSan, TSan). Use when writing, updating, or fixing C++ tests, configuring CTest or GoogleTest, investigating flaky test behavior, or setting up memory sanitizers for C++ test suites.
license: MIT
version: 0.1.0
---

# C++ Testing with GoogleTest and CTest

Flaky tests, silent memory corruption in test fixtures, and slow test discovery degrade confidence in test suites. Establishing a deterministic test harness with fast discovery and active sanitizers catches memory leaks and race conditions before code merges.

```bash
ctest --test-dir build --output-on-failure -j4
```

Detailed test fixture syntax, parameterized test suites, and CMake integration patterns are documented in [references/gtest-patterns.md](references/gtest-patterns.md).

## Core Concepts

1. **Red-Green-Refactor loop**: Write the failing assertion first, implement the minimum code to turn it green, then refactor with test verification.
2. **Isolation over integration**: Prefer fakes and explicit dependency injection rather than relying on shared global state.
3. **Structured directory layout**: Keep tests mirrored against source under `tests/unit/`, `tests/integration/`, and `tests/fixtures/`.
4. **Dynamic discovery**: Use `gtest_discover_tests()` in CMake so CTest registers tests automatically without manual listing.

## Writing Deterministic Tests

Prefer `EXPECT_*` for non-fatal checks that allow remaining assertions in the test to execute, and `ASSERT_*` when failure invalidates subsequent logic (such as checking pointer nullity before dereferencing).

```cpp
#include <gtest/gtest.h>

TEST(RingBufferTest, OverwriteAdvancesTail) {
    RingBuffer<int, 4> buffer;
    for (int i = 0; i < 5; ++i) {
        buffer.push(i);
    }
    EXPECT_EQ(buffer.size(), 4u);
    EXPECT_EQ(buffer.pop(), 1);
}
```

When verifying mocked interactions with GoogleMock:

```cpp
class MockHardwareBus : public HardwareBus {
public:
    MOCK_METHOD(bool, WriteRegister, (uint16_t reg, uint8_t val), (override));
    MOCK_METHOD(uint8_t, ReadRegister, (uint16_t reg), (override));
};
```

## Diagnosing Memory and Concurrency Bugs

Run tests under sanitizers by enabling compiler flags during configuration:
- AddressSanitizer (`-fsanitize=address`): Catches out-of-bounds accesses, use-after-free, and stack corruption.
- UndefinedBehaviorSanitizer (`-fsanitize=undefined`): Catches integer overflows, null pointer dereferences, and alignment violations.
- ThreadSanitizer (`-fsanitize=thread`): Detects data races in multithreaded test cases. Do not combine TSan with ASan in the same binary.

## Honest limits

Unit tests demonstrate the presence of specific verified behaviors, but cannot prove the absence of subtle hardware interactions, cache coherency anomalies, or platform-specific driver timing errors. Sanitizers introduce CPU and memory overhead, meaning timing-sensitive bugs in real-time loops may not manifest during sanitized test runs.
