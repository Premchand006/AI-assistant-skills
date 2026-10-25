# C++ Core Guidelines Reference

Detailed rule tables and patterns derived from the ISO C++ Core Guidelines.

## Philosophy & Interfaces (P.*, I.*)

| Rule | Summary |
|---|---|
| **P.1** | Express ideas directly in code |
| **P.3** | Express intent |
| **P.4** | Ideally, a program should be statically type safe |
| **P.5** | Prefer compile-time checking to run-time checking |
| **P.8** | Don't leak any resources |
| **P.10** | Prefer immutable data to mutable data |
| **I.1** | Make interfaces explicit |
| **I.2** | Avoid non-const global variables |
| **I.4** | Make interfaces precisely and strongly typed |
| **I.11** | Never transfer ownership by a raw pointer or reference |
| **I.23** | Keep the number of function arguments low |

## Functions (F.*)

| Rule | Summary |
|---|---|
| **F.1** | Package meaningful operations as carefully named functions |
| **F.2** | A function should perform a single logical operation |
| **F.3** | Keep functions short and simple |
| **F.4** | If a function might be evaluated at compile time, declare it `constexpr` |
| **F.6** | If your function must not throw, declare it `noexcept` |
| **F.8** | Prefer pure functions |
| **F.16** | For in-parameters, pass cheaply-copied types by value and others by `const&` |
| **F.20** | For out-values, prefer return values to output parameters |
| **F.21** | To return multiple out-values, prefer returning a struct |
| **F.43** | Never return a pointer or reference to a local object |

## Classes & Special Member Functions (C.*)

| Rule | Summary |
|---|---|
| **C.2** | Use `class` if an invariant exists; `struct` if data members vary independently |
| **C.9** | Minimize exposure of members |
| **C.20** | Rule of Zero: if default operations suffice, define none |
| **C.21** | Rule of Five: if defining any destructor/copy/move, declare all five |
| **C.35** | Base class destructor: public virtual or protected non-virtual |
| **C.41** | A constructor should create a fully initialized object |
| **C.46** | Declare single-argument constructors `explicit` |
| **C.67** | A polymorphic class should suppress public copy and move operations |
| **C.128** | Virtual functions: specify exactly one of `virtual`, `override`, or `final` |

## Resource Management (R.*)

| Rule | Summary |
|---|---|
| **R.1** | Manage resources automatically using resource handles (RAII) |
| **R.3** | A raw pointer is non-owning |
| **R.10** | Avoid `malloc()` and `free()` |
| **R.11** | Avoid calling `new` and `delete` explicitly; use `make_unique` or `make_shared` |
| **R.20** | Use `std::unique_ptr` to represent unique ownership |
| **R.21** | Prefer `std::unique_ptr` over `std::shared_ptr` unless sharing is genuinely required |

## Templates & Concepts (T.*)

| Rule | Summary |
|---|---|
| **T.1** | Use templates to raise the level of abstraction |
| **T.10** | Specify concepts for all template arguments |
| **T.11** | Use standard concepts whenever possible |
| **T.13** | Prefer shorthand notation for simple concepts |
| **T.43** | Prefer `using` over `typedef` |
| **T.144** | Do not specialize function templates; overload instead |

## Standard Library & Naming (SL.*, SF.*, NL.*)

| Rule | Summary |
|---|---|
| **SL.con.1** | Prefer `std::array` or `std::vector` over C-style arrays |
| **SL.con.2** | Prefer `std::vector` by default for dynamic sequences |
| **SL.str.1** | Use `std::string` to own character sequences |
| **SL.str.2** | Use `std::string_view` to refer to character sequences without ownership |
| **SL.io.50** | Avoid `std::endl` (use `'\n'`; `endl` forces a flush) |
| **SF.7** | Do not write `using namespace` at global scope in a header |
| **SF.8** | Use `#include` guards or `#pragma once` for all header files |
| **NL.5** | Avoid encoding type information in names (no Hungarian notation) |
| **NL.9** | Reserve all-caps naming strictly for preprocessor macros |
