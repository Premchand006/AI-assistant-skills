# GoogleTest and CTest Patterns

Practical recipes and CMake patterns for C++ testing.

## CMake and CTest Setup

```cmake
cmake_minimum_required(VERSION 3.20)
project(EngineTests CXX)

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
)
FetchContent_MakeAvailable(googletest)

enable_testing()

add_executable(unit_tests
  tests/unit/buffer_test.cpp
  tests/unit/parser_test.cpp
)

target_link_libraries(unit_tests PRIVATE GTest::gtest_main GTest::gmock)

include(GoogleTest)
gtest_discover_tests(unit_tests)
```

## Fixtures and Setup

```cpp
#include <gtest/gtest.h>

class DatabaseTest : public ::testing::Test {
protected:
    void SetUp() override {
        db_.connect(":memory:");
    }

    void TearDown() override {
        db_.disconnect();
    }

    MockDatabase db_;
};

TEST_F(DatabaseTest, InsertsRecordSuccessfully) {
    EXPECT_TRUE(db_.insert("key1", "val1"));
    EXPECT_EQ(db_.lookup("key1"), "val1");
}
```

## Parameterized Tests

```cpp
class MathIsPrimeTest : public ::testing::TestWithParam<std::pair<int, bool>> {};

TEST_P(MathIsPrimeTest, ValidatesPrimality) {
    auto [num, expected] = GetParam();
    EXPECT_EQ(is_prime(num), expected);
}

INSTANTIATE_TEST_SUITE_P(
    PrimeNumbers,
    MathIsPrimeTest,
    ::testing::Values(
        std::make_pair(2, true),
        std::make_pair(3, true),
        std::make_pair(4, false),
        std::make_pair(17, true),
        std::make_pair(25, false)
    )
);
```

## Sanitizers in CMake

```cmake
# Add memory and address sanitizers during development builds
if(ENABLE_SANITIZERS)
  target_compile_options(unit_tests PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
  target_link_options(unit_tests PRIVATE -fsanitize=address,undefined)
endif()
```
