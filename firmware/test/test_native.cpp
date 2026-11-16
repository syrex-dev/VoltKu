#include <unity.h>
#include <cstdio>
#include <cstring>
#include "../lib/energy_core/payload_formatter.hpp"
#include "../lib/energy_core/ring_buffer.hpp"

using namespace energy_core;

void setUp(void) {}
void tearDown(void) {}

void test_payload_formatting_and_golden_export(void) {
    TelemetrySample sample;
    sample.ts = 1736000000;
    sample.v = 220.5f;
    sample.i = 1.234f;
    sample.p = 272.1f;
    sample.e = 12.345f;
    sample.f = 50.0f;
    sample.pf = 0.98f;
    sample.rssi = -61;
    std::strncpy(sample.fw, "1.0.0", sizeof(sample.fw) - 1);
    sample.fw[sizeof(sample.fw) - 1] = '\0';

    char buffer[256];
    int len = format_telemetry_payload(buffer, sizeof(buffer), sample);
    TEST_ASSERT_GREATER_THAN(0, len);

    const char* expected = "{\"ts\":1736000000,\"v\":220.5,\"i\":1.234,\"p\":272.1,\"e\":12.345,\"f\":50.0,\"pf\":0.98,\"rssi\":-61,\"fw\":\"1.0.0\"}";
    TEST_ASSERT_EQUAL_STRING(expected, buffer);

    // Tulis ke golden_payload.json untuk divalidasi backend pytest
    FILE* fp = std::fopen("firmware/test/golden_payload.json", "w");
    if (!fp) {
        fp = std::fopen("test/golden_payload.json", "w");
    }
    TEST_ASSERT_NOT_NULL(fp);
    std::fputs(buffer, fp);
    std::fclose(fp);
}

void test_ring_buffer_fifo_push_and_drain(void) {
    TelemetryRingBuffer rb;
    TEST_ASSERT_TRUE(rb.empty());
    TEST_ASSERT_EQUAL_UINT32(0, rb.size());

    for (int i = 0; i < 5; ++i) {
        TelemetrySample s{};
        s.ts = 1731650000 + i * 10;
        s.p = 100.0f + i * 50.0f;
        rb.push(s);
    }
    TEST_ASSERT_EQUAL_UINT32(5, rb.size());

    // Drain secara FIFO
    for (int i = 0; i < 5; ++i) {
        size_t idx = 0;
        TelemetrySample out{};
        TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));
        TEST_ASSERT_EQUAL_INT64(1731650000 + i * 10, out.ts);

        uint16_t pkt_id = static_cast<uint16_t>(100 + i);
        TEST_ASSERT_TRUE(rb.mark_in_flight(idx, pkt_id));
        TEST_ASSERT_TRUE(rb.handle_puback(pkt_id));
    }

    TEST_ASSERT_TRUE(rb.empty());
    TEST_ASSERT_EQUAL_UINT32(0, rb.size());
    TEST_ASSERT_EQUAL_UINT32(0, rb.in_flight_count());
}

void test_ring_buffer_in_flight_limit(void) {
    TelemetryRingBuffer rb;
    for (int i = 0; i < 10; ++i) {
        TelemetrySample s{};
        s.ts = 1000 + i;
        rb.push(s);
    }

    // Ambil maks 4 paket in-flight
    for (uint16_t pid = 1; pid <= 4; ++pid) {
        size_t idx = 0;
        TelemetrySample out{};
        TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));
        TEST_ASSERT_TRUE(rb.mark_in_flight(idx, pid));
    }
    TEST_ASSERT_EQUAL_UINT32(4, rb.in_flight_count());

    // Paket ke-5 harus ditolak karena in-flight sudah 4
    size_t idx5 = 0;
    TelemetrySample out5{};
    TEST_ASSERT_FALSE(rb.get_next_pending(idx5, out5));

    // Terima PUBACK untuk paket 1
    TEST_ASSERT_TRUE(rb.handle_puback(1));
    TEST_ASSERT_EQUAL_UINT32(3, rb.in_flight_count());

    // Sekarang paket ke-5 dapat diambil
    TEST_ASSERT_TRUE(rb.get_next_pending(idx5, out5));
    TEST_ASSERT_TRUE(rb.mark_in_flight(idx5, 5));
    TEST_ASSERT_EQUAL_UINT32(4, rb.in_flight_count());
}

void test_ring_buffer_overflow_drop_oldest(void) {
    TelemetryRingBuffer rb;
    // Isi 360 sampel (penuh)
    for (int i = 0; i < 360; ++i) {
        TelemetrySample s{};
        s.ts = 1000 + i;
        rb.push(s);
    }
    TEST_ASSERT_EQUAL_UINT32(360, rb.size());
    TEST_ASSERT_EQUAL_UINT32(0, rb.overflow_count());

    // Push sampel ke-361 -> sampel tertua (ts=1000) ditimpa
    TelemetrySample s_new{};
    s_new.ts = 2000;
    rb.push(s_new);

    TEST_ASSERT_EQUAL_UINT32(360, rb.size());
    TEST_ASSERT_EQUAL_UINT32(1, rb.overflow_count());

    // Sampel terdepan sekarang adalah ts=1001
    size_t idx = 0;
    TelemetrySample out{};
    TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));
    TEST_ASSERT_EQUAL_INT64(1001, out.ts);
}

void test_ring_buffer_disconnect_requeues_in_flight(void) {
    TelemetryRingBuffer rb;
    for (int i = 0; i < 4; ++i) {
        TelemetrySample s{};
        s.ts = 1000 + i;
        rb.push(s);
    }

    for (uint16_t pid = 1; pid <= 4; ++pid) {
        size_t idx = 0;
        TelemetrySample out{};
        TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));
        TEST_ASSERT_TRUE(rb.mark_in_flight(idx, pid));
    }
    TEST_ASSERT_EQUAL_UINT32(4, rb.in_flight_count());

    // Simulasi putus koneksi (disconnect)
    rb.on_disconnect();
    TEST_ASSERT_EQUAL_UINT32(0, rb.in_flight_count());
    TEST_ASSERT_EQUAL_UINT32(4, rb.size());

    // Semua sampel harus kembali berstatus PENDING
    for (int i = 0; i < 4; ++i) {
        size_t idx = 0;
        TelemetrySample out{};
        TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));
        TEST_ASSERT_EQUAL_INT64(1000 + i, out.ts);
        TEST_ASSERT_TRUE(rb.mark_in_flight(idx, static_cast<uint16_t>(50 + i)));
    }
}

int main(int argc, char** argv) {
    UNITY_BEGIN();
    RUN_TEST(test_payload_formatting_and_golden_export);
    RUN_TEST(test_ring_buffer_fifo_push_and_drain);
    RUN_TEST(test_ring_buffer_in_flight_limit);
    RUN_TEST(test_ring_buffer_overflow_drop_oldest);
    RUN_TEST(test_ring_buffer_disconnect_requeues_in_flight);
    return UNITY_END();
}
