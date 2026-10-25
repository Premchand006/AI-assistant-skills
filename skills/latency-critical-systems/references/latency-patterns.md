# Latency-Critical Systems Engineering Reference

Practical patterns for low-latency, deterministic execution on modern x86_64 and ARM processors.

## Cache Line Alignment and False Sharing

Modern CPU cores share cache coherency lines (typically 64 bytes). When two independent threads write to variables residing on the same cache line, the cores constantly invalidate each other's L1/L2 caches ("false sharing"), creating major latency spikes.

```cpp
#include <new>

#ifdef __cpp_lib_hardware_interference_size
using std::hardware_destructive_interference_size;
#else
constexpr size_t hardware_destructive_interference_size = 64;
#endif

struct alignas(hardware_destructive_interference_size) ProducerState {
    uint64_t head{0};
};

struct alignas(hardware_destructive_interference_size) ConsumerState {
    uint64_t tail{0};
};
```

## Zero-Allocation Hot Paths

Dynamic memory allocation (`malloc`, `new`, `std::vector::push_back` triggering realloc) incurs unbounded execution latency from OS heap locks and page faults.

- Pre-allocate memory pools or ring buffers during startup.
- Store structures contiguously in pre-sized arrays.
- Avoid virtual function calls or pointer chasing in inner loops where inlining and branch prediction yield substantial gains.

## Lock-Free Single-Producer Single-Consumer (SPSC) Queue

For high-throughput message passing between two threads without lock contention:

```cpp
template <typename T, size_t Capacity>
class SPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity must be power of two");
public:
    bool push(const T& item) {
        const size_t current_head = head_.load(std::memory_order_relaxed);
        if ((current_head - tail_.load(std::memory_order_acquire)) >= Capacity) {
            return false; // Queue full
        }
        buffer_[current_head & (Capacity - 1)] = item;
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    bool pop(T& item) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        if (current_tail == head_.load(std::memory_order_acquire)) {
            return false; // Queue empty
        }
        item = buffer_[current_tail & (Capacity - 1)];
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

private:
    T buffer_[Capacity];
    alignas(64) std::atomic<size_t> head_{0};
    alignas(64) std::atomic<size_t> tail_{0};
};
```
