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

void test_ring_buffer_out_of_order_puback_maintains_full_capacity(void) {
    TelemetryRingBuffer rb;
    // 1. Masukkan 4 sampel
    for (int i = 0; i < 4; ++i) {
        TelemetrySample s{};
        s.ts = 1736000000LL + i;
        TEST_ASSERT_TRUE(rb.push(s));
    }
    TEST_ASSERT_EQUAL_UINT32(4, rb.size());

    // 2. Tandai keempatnya in-flight dengan packet_id 101, 102, 103, 104
    size_t indices[4];
    for (int i = 0; i < 4; ++i) {
        TelemetrySample out{};
        TEST_ASSERT_TRUE(rb.get_next_pending(indices[i], out));
        TEST_ASSERT_TRUE(rb.mark_in_flight(indices[i], static_cast<uint16_t>(101 + i)));
    }
    TEST_ASSERT_EQUAL_UINT32(4, rb.in_flight_count());

    // 3. Terima PUBACK out-of-order: ACK slot tengah (102 dan 103), slot 101 dan 104 tetap in-flight
    TEST_ASSERT_TRUE(rb.handle_puback(102));
    TEST_ASSERT_TRUE(rb.handle_puback(103));
    TEST_ASSERT_EQUAL_UINT32(2, rb.in_flight_count());
    TEST_ASSERT_EQUAL_UINT32(2, rb.size());

    // 4. Isi ulang buffer sampai penuh: karena kapasitas 360 dan sisa 2 item, harus bisa push 358 item
    for (int i = 0; i < 358; ++i) {
        TelemetrySample s{};
        s.ts = 1736001000LL + i;
        TEST_ASSERT_TRUE(rb.push(s));
    }
    // Kapasitas efektif harus persis 360 (tidak bocor/tersumbat karena slot tengah kosong)
    TEST_ASSERT_EQUAL_UINT32(360, rb.size());
    TEST_ASSERT_EQUAL_UINT32(0, rb.overflow_count());
    TEST_ASSERT_EQUAL_UINT32(360, rb.count_non_empty_slots());

    // 5. Push 1 lagi -> baru overflow terjadi (360 tetap penuh)
    TelemetrySample s_overflow{};
    s_overflow.ts = 1736009999LL;
    TEST_ASSERT_TRUE(rb.push(s_overflow));
    TEST_ASSERT_EQUAL_UINT32(360, rb.size());
    TEST_ASSERT_EQUAL_UINT32(1, rb.overflow_count());
}

void test_ring_buffer_overwritten_in_flight_slot_delayed_puback_ignored(void) {
    TelemetryRingBuffer rb;
    // 1. Isi penuh 360 sampel
    for (int i = 0; i < 360; ++i) {
        TelemetrySample s{};
        s.ts = 1736000000LL + i;
        TEST_ASSERT_TRUE(rb.push(s));
    }
    TEST_ASSERT_EQUAL_UINT32(360, rb.size());

    // 2. Ambil sampel tertua (index paling awal) dan tandai in-flight dengan packet_id 555
    size_t idx0 = 0;
    TelemetrySample out0{};
    TEST_ASSERT_TRUE(rb.get_next_pending(idx0, out0));
    TEST_ASSERT_EQUAL_INT64(1736000000LL, out0.ts);
    TEST_ASSERT_TRUE(rb.mark_in_flight(idx0, 555));
    TEST_ASSERT_EQUAL_UINT32(1, rb.in_flight_count());

    // 3. Masukkan 1 sampel baru saat buffer penuh -> sampel tertua (in-flight 555) ditimpa
    TelemetrySample s_new{};
    s_new.ts = 1736050000LL;
    TEST_ASSERT_TRUE(rb.push(s_new));
    TEST_ASSERT_EQUAL_UINT32(360, rb.size());
    TEST_ASSERT_EQUAL_UINT32(1, rb.overflow_count());
    // In-flight count harus didekrementasi saat slot in-flight ditimpa
    TEST_ASSERT_EQUAL_UINT32(0, rb.in_flight_count());

    // 4. PUBACK terlambat untuk packet_id 555 datang kemudian -> harus diabaikan (false)
    TEST_ASSERT_FALSE(rb.handle_puback(555));

    // 5. Pastikan integritas buffer tetap sempurna
    TEST_ASSERT_EQUAL_UINT32(360, rb.size());
    TEST_ASSERT_EQUAL_UINT32(0, rb.in_flight_count());
    TEST_ASSERT_EQUAL_UINT32(1, rb.overflow_count());
    TEST_ASSERT_EQUAL_UINT32(360, rb.count_non_empty_slots());

    // Sampel terdepan saat ini adalah ts=1736000001
    size_t next_idx = 0;
    TelemetrySample next_out{};
    TEST_ASSERT_TRUE(rb.get_next_pending(next_idx, next_out));
    TEST_ASSERT_EQUAL_INT64(1736000001LL, next_out.ts);
}

void test_ring_buffer_1000_random_cycles_invariant_count_equals_non_empty(void) {
    TelemetryRingBuffer rb;
    uint32_t seed = 123456789;
    auto lcg_rand = [&seed]() -> uint32_t {
        seed = seed * 1664525u + 1013904223u;
        return seed;
    };

    uint16_t next_pkt_id = 1;
    uint16_t active_pkt_ids[16];
    size_t active_pkt_count = 0;
    int64_t current_ts = 1736000000LL;

    for (int cycle = 0; cycle < 1000; ++cycle) {
        uint32_t action = lcg_rand() % 5;
        if (action == 0 || action == 1) {
            // Push
            TelemetrySample s{};
            s.ts = ++current_ts;
            s.p = static_cast<float>(lcg_rand() % 5000);
            rb.push(s);
        } else if (action == 2) {
            // Get next pending & mark in flight
            size_t idx = 0;
            TelemetrySample out{};
            if (rb.get_next_pending(idx, out)) {
                uint16_t pid = next_pkt_id++;
                if (pid == 0) pid = next_pkt_id++;
                if (rb.mark_in_flight(idx, pid)) {
                    if (active_pkt_count < 16) {
                        active_pkt_ids[active_pkt_count++] = pid;
                    }
                }
            }
        } else if (action == 3) {
            // Handle PUBACK
            if (active_pkt_count > 0) {
                size_t p_idx = lcg_rand() % active_pkt_count;
                uint16_t pid = active_pkt_ids[p_idx];
                active_pkt_ids[p_idx] = active_pkt_ids[active_pkt_count - 1];
                --active_pkt_count;
                rb.handle_puback(pid);
            } else {
                rb.handle_puback(static_cast<uint16_t>(lcg_rand() % 500));
            }
        } else if (action == 4) {
            if ((lcg_rand() % 20) == 0) {
                rb.on_disconnect();
                active_pkt_count = 0;
            }
        }

        // Invarian mutlak: count_ (rb.size()) == jumlah slot non-EMPTY di storage
        TEST_ASSERT_EQUAL_UINT32(rb.size(), rb.count_non_empty_slots());
        TEST_ASSERT_LESS_OR_EQUAL_UINT32(360, rb.size());
        TEST_ASSERT_LESS_OR_EQUAL_UINT32(4, rb.in_flight_count());
    }
}

void test_ring_buffer_early_ack_before_mark_frees_slot_immediately() {
    TelemetryRingBuffer rb;
    TelemetrySample s{};
    s.ts = 1736000000LL;
    s.v = 220.0f;
    s.p = 500.0f;
    TEST_ASSERT_TRUE(rb.push(s));
    TEST_ASSERT_EQUAL_UINT32(1, rb.size());

    size_t idx = 0;
    TelemetrySample out{};
    TEST_ASSERT_TRUE(rb.get_next_pending(idx, out));

    // Skenario: PUBACK tiba SEBELUM mark_in_flight dipanggil
    uint16_t packet_id = 105;
    TEST_ASSERT_FALSE(rb.handle_puback(packet_id));
    TEST_ASSERT_TRUE(rb.has_early_ack(packet_id));
    TEST_ASSERT_EQUAL_UINT32(1, rb.early_acks_count());
    TEST_ASSERT_EQUAL_UINT32(1, rb.size());

    // Saat mark_in_flight dipanggil dengan packet_id yang sudah di-ACK duluan:
    // Slot langsung dibebaskan seketika tanpa pernah menjadi IN_FLIGHT!
    TEST_ASSERT_TRUE(rb.mark_in_flight(idx, packet_id));
    TEST_ASSERT_EQUAL_UINT32(0, rb.size());
    TEST_ASSERT_EQUAL_UINT32(0, rb.in_flight_count());
    TEST_ASSERT_FALSE(rb.has_early_ack(packet_id));
    TEST_ASSERT_EQUAL_UINT32(0, rb.early_acks_count());
}

void test_ring_buffer_double_early_ack_and_normal_double_ack() {
    TelemetryRingBuffer rb;
    uint16_t pid = 77;

    // 1. Double early ACK
    rb.handle_puback(pid);
    rb.handle_puback(pid);
    TEST_ASSERT_EQUAL_UINT32(1, rb.early_acks_count());
    TEST_ASSERT_TRUE(rb.has_early_ack(pid));

    // 2. Double ACK pada slot normal
    TelemetrySample s{};
    s.ts = 1736000000LL;
    rb.push(s);
    size_t idx = 0;
    TelemetrySample out{};
    rb.get_next_pending(idx, out);
    rb.mark_in_flight(idx, 88);
    TEST_ASSERT_TRUE(rb.handle_puback(88)); // Berhasil free slot
    TEST_ASSERT_FALSE(rb.handle_puback(88)); // ACK ganda kedua: ditangani anggun tanpa crash
}

void test_ring_buffer_early_acks_overflow_drops_oldest() {
    TelemetryRingBuffer rb;

    // Isi early_acks hingga kapasitas penuh (16 entri)
    for (uint16_t i = 1; i <= 16; ++i) {
        rb.handle_puback(i);
    }
    TEST_ASSERT_EQUAL_UINT32(16, rb.early_acks_count());
    TEST_ASSERT_TRUE(rb.has_early_ack(1));
    TEST_ASSERT_TRUE(rb.has_early_ack(16));

    // Tambah entri ke-17: entri tertua (id=1) harus dibuang secara FIFO tanpa crash
    rb.handle_puback(17);
    TEST_ASSERT_EQUAL_UINT32(16, rb.early_acks_count());
    TEST_ASSERT_FALSE(rb.has_early_ack(1));
    TEST_ASSERT_TRUE(rb.has_early_ack(17));
}

void test_ring_buffer_disconnect_clears_early_acks() {
    TelemetryRingBuffer rb;
    rb.handle_puback(501);
    rb.handle_puback(502);
    TEST_ASSERT_EQUAL_UINT32(2, rb.early_acks_count());

    rb.on_disconnect();
    TEST_ASSERT_EQUAL_UINT32(0, rb.early_acks_count());
    TEST_ASSERT_FALSE(rb.has_early_ack(501));
    TEST_ASSERT_FALSE(rb.has_early_ack(502));
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
    RUN_TEST(test_ring_buffer_out_of_order_puback_maintains_full_capacity);
    RUN_TEST(test_ring_buffer_overwritten_in_flight_slot_delayed_puback_ignored);
    RUN_TEST(test_ring_buffer_1000_random_cycles_invariant_count_equals_non_empty);
    RUN_TEST(test_ring_buffer_early_ack_before_mark_frees_slot_immediately);
    RUN_TEST(test_ring_buffer_double_early_ack_and_normal_double_ack);
    RUN_TEST(test_ring_buffer_early_acks_overflow_drops_oldest);
    RUN_TEST(test_ring_buffer_disconnect_clears_early_acks);
    return UNITY_END();
}
