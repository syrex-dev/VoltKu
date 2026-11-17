#pragma once

#include <cstddef>
#include <cstdint>
#include "payload_formatter.hpp"

namespace energy_core {

constexpr size_t BUFFER_CAPACITY = 360;
constexpr size_t MAX_IN_FLIGHT = 4;
constexpr int64_t MIN_VALID_TIMESTAMP = 1735689600LL; // 2025-01-01 00:00:00 UTC
constexpr size_t MAX_DRAIN_PER_SECOND = 5;
constexpr size_t MAX_EARLY_ACKS = 16;

/**
 * Pengatur laju kuras (drain rate limiter) deterministik:
 * Membatasi maksimal 5 transmisi sampel per detik (jendela geser 1000ms).
 */
class DrainRateLimiter {
public:
    explicit DrainRateLimiter(size_t max_per_second = MAX_DRAIN_PER_SECOND)
        : max_per_second_(max_per_second),
          window_start_ms_(0),
          drain_count_(0) {}

    bool can_drain(uint32_t now_ms) {
        if (now_ms - window_start_ms_ >= 1000) {
            window_start_ms_ = now_ms;
            drain_count_ = 0;
        }
        return drain_count_ < max_per_second_;
    }

    bool record_drain(uint32_t now_ms) {
        if (!can_drain(now_ms)) {
            return false;
        }
        ++drain_count_;
        return true;
    }

    size_t count_in_window() const { return drain_count_; }

    void reset() {
        window_start_ms_ = 0;
        drain_count_ = 0;
    }

private:
    size_t max_per_second_;
    uint32_t window_start_ms_;
    size_t drain_count_;
};

enum class SlotState : uint8_t {
    EMPTY = 0,
    PENDING = 1,
    IN_FLIGHT = 2,
};

struct BufferSlot {
    TelemetrySample sample;
    uint16_t packet_id;
    SlotState state;
};

class TelemetryRingBuffer {
public:
    TelemetryRingBuffer() {
        clear();
    }

    /**
     * Memasukkan sampel baru ke dalam ring buffer (FIFO).
     * Guard NTP: Sampel dengan ts < 1735689600 (sebelum 2025-01-01) DITOLAK
     * dan tidak masuk buffer.
     * Desain Bebas Head-of-Line Blocking:
     * Pemisahan 'storage' (slot pool) dan 'ordering' (antrean indeks FIFO).
     * Jika buffer penuh (360 sampel), sampel terlama di antrean aktif ditimpa (drop oldest)
     * dan counter overflow bertambah.
     */
    bool push(const TelemetrySample& sample) {
        if (sample.ts < MIN_VALID_TIMESTAMP) {
            return false;
        }

        if (active_count_ >= BUFFER_CAPACITY) {
            // Buffer penuh: timpa sampel terlama (posisi 0 di antrean aktif)
            size_t oldest_slot = active_indices_[0];
            if (slots_[oldest_slot].state == SlotState::IN_FLIGHT) {
                if (in_flight_count_ > 0) {
                    --in_flight_count_;
                }
            }
            slots_[oldest_slot].state = SlotState::EMPTY;
            slots_[oldest_slot].packet_id = 0;

            // Kembalikan slot tertua ke pool slot bebas
            free_slots_[free_count_++] = oldest_slot;

            // Geser antrean aktif maju satu posisi
            for (size_t i = 1; i < active_count_; ++i) {
                active_indices_[i - 1] = active_indices_[i];
            }
            --active_count_;
            ++overflow_count_;
        }

        // Alokasikan slot dari pool bebas
        size_t new_slot = free_slots_[--free_count_];
        slots_[new_slot].sample = sample;
        slots_[new_slot].packet_id = 0;
        slots_[new_slot].state = SlotState::PENDING;

        // Tambahkan ke ujung antrean ordering
        active_indices_[active_count_++] = new_slot;
        return true;
    }

    /**
     * Mengambil sampel berikutnya yang berstatus PENDING untuk dikirim secara FIFO.
     * Mengembalikan false jika tidak ada sampel pending atau in-flight sudah mencapai batas MAX_IN_FLIGHT (4).
     */
    bool get_next_pending(size_t& out_index, TelemetrySample& out_sample) {
        if (in_flight_count_ >= MAX_IN_FLIGHT || active_count_ == 0) {
            return false;
        }

        for (size_t i = 0; i < active_count_; ++i) {
            size_t slot_idx = active_indices_[i];
            if (slots_[slot_idx].state == SlotState::PENDING) {
                out_index = slot_idx;
                out_sample = slots_[slot_idx].sample;
                return true;
            }
        }

        return false;
    }

    /**
     * Menandai slot pada index tertentu sebagai IN_FLIGHT dengan packet_id MQTT.
     * Jika PUBACK untuk packet_id ini sudah tiba lebih awal (early ACK sebelum mark),
     * slot langsung dibebaskan seketika dan kapasitas pulih tanpa pernah menjadi IN_FLIGHT.
     */
    bool mark_in_flight(size_t index, uint16_t packet_id) {
        if (index >= BUFFER_CAPACITY || packet_id == 0) {
            return false;
        }
        if (slots_[index].state != SlotState::PENDING) {
            return false;
        }

        // Periksa apakah PUBACK untuk packet_id ini sudah tiba lebih dulu (early ACK)
        if (remove_early_ack(packet_id)) {
            // Slot langsung dibebaskan seketika
            slots_[index].state = SlotState::EMPTY;
            slots_[index].packet_id = 0;

            free_slots_[free_count_++] = index;

            // Keluarkan index dari antrean aktif (active_indices_)
            for (size_t i = 0; i < active_count_; ++i) {
                if (active_indices_[i] == index) {
                    for (size_t j = i + 1; j < active_count_; ++j) {
                        active_indices_[j - 1] = active_indices_[j];
                    }
                    --active_count_;
                    break;
                }
            }
            return true;
        }

        slots_[index].state = SlotState::IN_FLIGHT;
        slots_[index].packet_id = packet_id;
        ++in_flight_count_;
        return true;
    }

    /**
     * Dipanggil saat konfirmasi PUBACK diterima dari broker MQTT.
     * Mendukung PUBACK di luar urutan (out-of-order PUBACK) tanpa head-of-line blocking:
     * Slot yang di-ACK langsung dilepaskan ke pool bebas dan kapasitas seketika pulih.
     * Jika packet_id belum dikenal (mis. PUBACK tiba SEBELUM mark_in_flight),
     * packet_id disimpan ke himpunan early_acks berkapasitas tetap (maks 16).
     * Jika early_acks penuh, entri tertua dibuang secara FIFO tanpa crash.
     */
    bool handle_puback(uint16_t packet_id) {
        if (packet_id == 0) {
            return false;
        }

        for (size_t i = 0; i < active_count_; ++i) {
            size_t slot_idx = active_indices_[i];
            if (slots_[slot_idx].state == SlotState::IN_FLIGHT && slots_[slot_idx].packet_id == packet_id) {
                slots_[slot_idx].state = SlotState::EMPTY;
                slots_[slot_idx].packet_id = 0;
                if (in_flight_count_ > 0) {
                    --in_flight_count_;
                }

                // Kembalikan slot ke pool bebas
                free_slots_[free_count_++] = slot_idx;

                // Geser antrean aktif untuk mengeluarkan slot yang di-ACK
                for (size_t j = i + 1; j < active_count_; ++j) {
                    active_indices_[j - 1] = active_indices_[j];
                }
                --active_count_;
                return true;
            }
        }

        // Packet id belum dikenal (tiba sebelum mark_in_flight atau entri slot telah terhapus)
        record_early_ack(packet_id);
        return false;
    }

    /**
     * Penanganan saat koneksi terputus:
     * Semua slot IN_FLIGHT yang belum menerima PUBACK dikembalikan menjadi PENDING
     * agar dapat ditransmisikan ulang saat tersambung kembali sesuai urutan FIFO aslinya.
     * Himpunan early_acks dibersihkan.
     */
    void on_disconnect() {
        for (size_t i = 0; i < active_count_; ++i) {
            size_t slot_idx = active_indices_[i];
            if (slots_[slot_idx].state == SlotState::IN_FLIGHT) {
                slots_[slot_idx].state = SlotState::PENDING;
                slots_[slot_idx].packet_id = 0;
            }
        }
        in_flight_count_ = 0;
        early_acks_count_ = 0;
    }

    size_t size() const { return active_count_; }
    size_t in_flight_count() const { return in_flight_count_; }
    uint32_t overflow_count() const { return overflow_count_; }
    bool empty() const { return active_count_ == 0; }
    size_t early_acks_count() const { return early_acks_count_; }

    bool has_early_ack(uint16_t packet_id) const {
        if (packet_id == 0) return false;
        for (size_t i = 0; i < early_acks_count_; ++i) {
            if (early_acks_[i] == packet_id) {
                return true;
            }
        }
        return false;
    }

    size_t count_non_empty_slots() const {
        size_t non_empty = 0;
        for (size_t i = 0; i < BUFFER_CAPACITY; ++i) {
            if (slots_[i].state != SlotState::EMPTY) {
                ++non_empty;
            }
        }
        return non_empty;
    }

    void clear() {
        active_count_ = 0;
        in_flight_count_ = 0;
        overflow_count_ = 0;
        free_count_ = BUFFER_CAPACITY;
        early_acks_count_ = 0;
        for (size_t i = 0; i < BUFFER_CAPACITY; ++i) {
            slots_[i].state = SlotState::EMPTY;
            slots_[i].packet_id = 0;
            free_slots_[i] = i;
        }
    }

private:
    void record_early_ack(uint16_t packet_id) {
        if (packet_id == 0) {
            return;
        }
        // Jika sudah ada (ACK ganda), abaikan tanpa duplikasi
        if (has_early_ack(packet_id)) {
            return;
        }
        // Jika kapasitas early_acks penuh, buang entri tertua (FIFO)
        if (early_acks_count_ >= MAX_EARLY_ACKS) {
            for (size_t i = 1; i < early_acks_count_; ++i) {
                early_acks_[i - 1] = early_acks_[i];
            }
            --early_acks_count_;
        }
        early_acks_[early_acks_count_++] = packet_id;
    }

    bool remove_early_ack(uint16_t packet_id) {
        if (packet_id == 0) {
            return false;
        }
        for (size_t i = 0; i < early_acks_count_; ++i) {
            if (early_acks_[i] == packet_id) {
                for (size_t j = i + 1; j < early_acks_count_; ++j) {
                    early_acks_[j - 1] = early_acks_[j];
                }
                --early_acks_count_;
                return true;
            }
        }
        return false;
    }

    BufferSlot slots_[BUFFER_CAPACITY];
    size_t free_slots_[BUFFER_CAPACITY];
    size_t free_count_;
    size_t active_indices_[BUFFER_CAPACITY];
    size_t active_count_;
    size_t in_flight_count_;
    uint32_t overflow_count_;
    uint16_t early_acks_[MAX_EARLY_ACKS];
    size_t early_acks_count_;
};

} // namespace energy_core

