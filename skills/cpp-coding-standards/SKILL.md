---
name: cpp-coding-standards
description: Enforce modern C++ guidelines (C++17/20/23) derived from the ISO C++ Core Guidelines. Covers RAII, resource ownership, const-correctness, Rule of Zero and Five, smart pointer selection, bounds safety, concepts, and avoiding undefined behavior. Use when writing, reviewing, or refactoring C++ code, headers, classes, or systems modules, or when checking that C++ interfaces enforce memory and type safety at compile time.
license: MIT
version: 0.1.0
---

# Modern C++ Standards (ISO C++ Core Guidelines)

The bugs that cost the most in C++ arise from ambiguous resource ownership, dangling pointers, uninitialized state, and silent slicing during polymorphic copies. The ISO C++ Core Guidelines eliminate these classes of defects by relying on the compiler's type system, value semantics, and deterministic resource destruction.

```cpp
// RAII and value semantics: no explicit memory calls required
auto buffer = std::make_unique<uint8_t[]>(length);
std::span<const uint8_t> view(buffer.get(), length);
```

Extended rule tables and cross-cutting guideline mappings live in [references/core-guidelines.md](references/core-guidelines.md). Consult that reference when deciding between language features or verifying specific rule numbers (P, I, F, C, R, T, SL).

## Core Principles

1. **RAII everywhere**: Tie resource acquisition and release directly to object lifetimes. Raw `new` and `delete` should not appear in application code.
2. **Immutability by default**: Mark data members and variables `const` or `constexpr` unless mutation is required.
3. **Value semantics**: Prefer returning values or structured bindings rather than passing output parameters.
4. **Compile-time enforcement**: Prefer `static_assert` and C++20 concepts over runtime dynamic checks where feasible.

## Ownership and Pointers

A raw pointer represents an observation, not an owner. An interface that receives a raw pointer assumes the caller manages lifetime.

```cpp
// Explicit ownership transfer via unique_ptr
void ingest(std::unique_ptr<Packet> packet);

// Borrowed view: non-owning observation
void inspect(const Packet& packet);
void inspect_range(std::span<const uint8_t> bytes);
```

When shared ownership is genuinely necessary across independent async subsystems, use `std::shared_ptr`. Otherwise, prefer `std::unique_ptr` because it avoids atomic reference counting overhead.

## Rule of Zero and Rule of Five

A class that relies on standard containers (`std::vector`, `std::string`, `std::unique_ptr`) requires no custom copy, move, or destructor logic. This is the **Rule of Zero**.

```cpp
struct Session {
    std::string id;
    std::vector<uint8_t> payload;
    std::unique_ptr<SocketHandle> socket;
    // Special member functions generated automatically by compiler
};
```

If a class directly wraps a low-level OS handle or hardware resource, handle all special members explicitly (**Rule of Five**):
1. Destructor
2. Copy constructor
3. Copy assignment operator
4. Move constructor
5. Move assignment operator

Polymorphic base classes should declare their destructor `public virtual` or `protected non-virtual` to avoid undefined behavior during deletion.

## Interfaces and Parameter Passing

- Pass cheaply copied types (e.g., primitives, `std::string_view`, `std::span`) by value.
- Pass expensive or polymorphic types by `const&`.
- Single-argument constructors should be marked `explicit` to prevent unintended implicit conversions.
- Scoped enumerations (`enum class`) prevent unscoped identifier collisions.

```cpp
enum class Channel : uint8_t {
    primary,
    backup,
    telemetry
};

class Node {
public:
    explicit Node(std::string_view identifier);
};
```

## Honest limits

This skill enforces stylistic and architectural guidelines. It does not replace a static analysis engine (such as clang-tidy or SonarQube) or a dynamic memory sanitizer (ASan/TSan). Adhering to the Core Guidelines minimizes runtime defects, but cannot mathematically prove freedom from race conditions or lock contention in complex multithreaded systems.
