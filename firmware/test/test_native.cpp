#include <unity.h>
#include <cstdio>
#include <cstring>
#include <payload_formatter.hpp>
#include <ring_buffer.hpp>

using namespace energy_core;

void setUp(void) {}
void tearDown(void) {}

void test_payload_formatting_and_golden_export(void) {
    TelemetrySample sample{};
    sample.v = 220.5f;
    sample.i = 1.234f;
    sample.p = 272.1f;
    sample.e = 12.345f;
    sample.f = 50.0f;
    sample.pf = 0.98f;
    sample.rssi = -61;
    std::strncpy(sample.fw, "1.0.0", sizeof(sample.fw) - 1);
    sample.ts = 1736000000LL;

    char buffer[256];
    int len = format_telemetry_payload(buffer, sizeof(buffer), sample);

    TEST_ASSERT_GREATER_THAN(0, len);
    TEST_ASSERT_NOT_NULL(std::strstr(buffer, "\"v\":220.5"));
    TEST_ASSERT_NOT_NULL(std::strstr(buffer, "\"i\":1.234"));
    TEST_ASSERT_NOT_NULL(std::strstr(buffer, "\"p\":272.1"));
    TEST_ASSERT_NOT_NULL(std::strstr(buffer, "\"e\":12.345"));
    TEST_ASSERT_NOT_NULL(std::strstr(buffer, "\"f\":50.0"));
    TEST_ASSERT_NOT_NULL(std::strstr(buffer, "\"pf\":0.98"));
    TEST_ASSERT_NOT_NULL(std::strstr(buffer, "\"rssi\":-61"));
    TEST_ASSERT_NOT_NULL(std::strstr(buffer, "\"fw\":\"1.0.0\""));
    TEST_ASSERT_NOT_NULL(std::strstr(buffer, "\"ts\":1736000000"));

    // Ekspor golden payload ke test/golden_payload.json
    FILE* f = std::fopen("test/golden_payload.json", "w");
    if (!f) {
        f = std::fopen("golden_payload.json", "w");
    }
    if (f) {
        std::fputs(buffer, f);
        std::fclose(f);
    }
}

void test_ring_buffer_fifo_push_and_drain(void) {
    TelemetryRingBuffer rb;
    TEST_ASSERT_TRUE(rb.empty());
    TEST_ASSERT_EQUAL_UINT32(0, rb.size());

    // Masukkan 5 sampel valid
    for (int i = 0; i < 5; ++i) {
        TelemetrySample s{};
        s.ts = 1736000000LL + i * 10;
        s.p = 100.0f + i * 50.0f;
        TEST_ASSERT_TRUE(rb.push(s));
    }
    TEST_ASSERT_EQUAL_UINT32(5, rb.size());

    // Drain secara FIFO
    for (int i = 0; i < 5; ++i) {
        size_t idx = 0;
        TelemetrySample out{};
        TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));
        TEST_ASSERT_EQUAL_INT64(1736000000LL + i * 10, out.ts);

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
        s.ts = 1736000000LL + i;
        TEST_ASSERT_TRUE(rb.push(s));
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
        s.ts = 1736000000LL + i;
        TEST_ASSERT_TRUE(rb.push(s));
    }
    TEST_ASSERT_EQUAL_UINT32(360, rb.size());
    TEST_ASSERT_EQUAL_UINT32(0, rb.overflow_count());

    // Push sampel ke-361 -> sampel tertua (ts=1736000000) ditimpa
    TelemetrySample s_new{};
    s_new.ts = 1736005000LL;
    TEST_ASSERT_TRUE(rb.push(s_new));

    TEST_ASSERT_EQUAL_UINT32(360, rb.size());
    TEST_ASSERT_EQUAL_UINT32(1, rb.overflow_count());

    // Sampel terdepan sekarang adalah ts=1736000001
    size_t idx = 0;
    TelemetrySample out{};
    TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));
    TEST_ASSERT_EQUAL_INT64(1736000001LL, out.ts);
}

void test_ring_buffer_disconnect_requeues_in_flight(void) {
    TelemetryRingBuffer rb;
    for (int i = 0; i < 4; ++i) {
        TelemetrySample s{};
        s.ts = 1736000000LL + i;
        TEST_ASSERT_TRUE(rb.push(s));
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
        TEST_ASSERT_EQUAL_INT64(1736000000LL + i, out.ts);
        TEST_ASSERT_TRUE(rb.mark_in_flight(idx, static_cast<uint16_t>(50 + i)));
    }
}

void test_ring_buffer_rejects_samples_before_valid_ntp_time(void) {
    TelemetryRingBuffer rb;

    // Sampel sebelum 2025-01-01 (epoch < 1735689600) harus ditolak
    TelemetrySample invalid_sample{};
    invalid_sample.ts = 1000LL;
    TEST_ASSERT_FALSE(rb.push(invalid_sample));
    TEST_ASSERT_EQUAL_UINT32(0, rb.size());

    TelemetrySample invalid_edge{};
    invalid_edge.ts = 1735689599LL;
    TEST_ASSERT_FALSE(rb.push(invalid_edge));
    TEST_ASSERT_EQUAL_UINT32(0, rb.size());

    // Sampel tepat batas valid (1735689600) diterima
    TelemetrySample valid_sample{};
    valid_sample.ts = 1735689600LL;
    TEST_ASSERT_TRUE(rb.push(valid_sample));
    TEST_ASSERT_EQUAL_UINT32(1, rb.size());
}

void test_ring_buffer_puback_unknown_packet_id_ignored(void) {
    TelemetryRingBuffer rb;
    TelemetrySample s{};
    s.ts = 1736000000LL;
    rb.push(s);

    size_t idx = 0;
    TelemetrySample out{};
    TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));
    TEST_ASSERT_TRUE(rb.mark_in_flight(idx, 42));
    TEST_ASSERT_EQUAL_UINT32(1, rb.in_flight_count());

    // PUBACK packetId tak dikenal diabaikan
    TEST_ASSERT_FALSE(rb.handle_puback(999));
    TEST_ASSERT_FALSE(rb.handle_puback(0));
    TEST_ASSERT_EQUAL_UINT32(1, rb.in_flight_count());
    TEST_ASSERT_EQUAL_UINT32(1, rb.size());
}

void test_ring_buffer_double_puback_handled_gracefully(void) {
    TelemetryRingBuffer rb;
    TelemetrySample s{};
    s.ts = 1736000000LL;
    rb.push(s);

    size_t idx = 0;
    TelemetrySample out{};
    TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));
    TEST_ASSERT_TRUE(rb.mark_in_flight(idx, 77));
    TEST_ASSERT_EQUAL_UINT32(1, rb.in_flight_count());

    // ACK pertama berhasil
    TEST_ASSERT_TRUE(rb.handle_puback(77));
    TEST_ASSERT_EQUAL_UINT32(0, rb.in_flight_count());
    TEST_ASSERT_EQUAL_UINT32(0, rb.size());

    // ACK ganda (kedua) diabaikan tanpa membuat in_flight_count underflow
    TEST_ASSERT_FALSE(rb.handle_puback(77));
    TEST_ASSERT_EQUAL_UINT32(0, rb.in_flight_count());
    TEST_ASSERT_EQUAL_UINT32(0, rb.size());
}

void test_drain_rate_limiter_max_5_per_second(void) {
    DrainRateLimiter limiter;

    uint32_t t = 1000;
    // 5 drain dalam jendela 1 detik pertama harus berhasil
    for (int i = 0; i < 5; ++i) {
        TEST_ASSERT_TRUE(limiter.can_drain(t));
        TEST_ASSERT_TRUE(limiter.record_drain(t));
    }
    TEST_ASSERT_EQUAL_UINT32(5, limiter.count_in_window());

    // Drain ke-6 dalam jendela waktu yang sama (t=1000) harus ditolak
    TEST_ASSERT_FALSE(limiter.can_drain(t));
    TEST_ASSERT_FALSE(limiter.record_drain(t));
    TEST_ASSERT_EQUAL_UINT32(5, limiter.count_in_window());

    // Setelah 1000ms berlalu (t=2000), jendela baru terbuka dan dapat menguras kembali
    uint32_t t_next = 2000;
    TEST_ASSERT_TRUE(limiter.can_drain(t_next));
    TEST_ASSERT_TRUE(limiter.record_drain(t_next));
    TEST_ASSERT_EQUAL_UINT32(1, limiter.count_in_window());
}

int main(int argc, char** argv) {
    UNITY_BEGIN();
    RUN_TEST(test_payload_formatting_and_golden_export);
    RUN_TEST(test_ring_buffer_fifo_push_and_drain);
    RUN_TEST(test_ring_buffer_in_flight_limit);
    RUN_TEST(test_ring_buffer_overflow_drop_oldest);
    RUN_TEST(test_ring_buffer_disconnect_requeues_in_flight);
    RUN_TEST(test_ring_buffer_rejects_samples_before_valid_ntp_time);
    RUN_TEST(test_ring_buffer_puback_unknown_packet_id_ignored);
    RUN_TEST(test_ring_buffer_double_puback_handled_gracefully);
    RUN_TEST(test_drain_rate_limiter_max_5_per_second);
    return UNITY_END();
}
