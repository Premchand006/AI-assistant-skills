/* Fixture: firmware with the concurrency bugs the checker should find.
 * Every defect here is deliberate. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#define SCALE(x) x * 2              /* unparenthesised macro */

static uint32_t rx_count;           /* shared with the ISR, not volatile */
volatile uint32_t tick_ms;
static uint8_t  rx_buf[64];

void USART1_IRQHandler(void)
{
    uint8_t byte = (uint8_t)(USART1->RDR & 0xFFU);

    printf("rx %02x\n", byte);      /* blocks for milliseconds in a handler */

    rx_buf[rx_count] = byte;
    rx_count = rx_count + 1U;

    while ((USART1->ISR & USART_ISR_TXE) == 0U);   /* busy-wait, no timeout */
}

void SysTick_Handler(void)
{
    tick_ms++;
}

void main_loop(void)
{
    for (;;) {
        if (rx_count > 0U) {
            rx_count--;             /* read-modify-write, no critical section */
            process(rx_buf[rx_count]);
        }
        uint8_t *scratch = malloc(128);   /* heap in firmware */
        free(scratch);
    }
}
