import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, it, expect } from 'vitest'
import { PlanUpgradeModal } from '../PlanUpgradeModal'
import { ProfileModal } from '../ProfileModal'
import { SettingsView } from '../SettingsView'
import { HeroBannerCarousel } from '../HeroBannerCarousel'
import { AdminHeroBannersCard } from '../AdminHeroBannersCard'
import { AdminPanel } from '../AdminPanel'
import { AiChatWidget } from '../AiChatWidget'
import { AnomaliesList } from '../AnomaliesList'
import { OnboardingTour } from '../OnboardingTour'
import { UsageGuideModal } from '../UsageGuideModal'
import { Header } from '../Header'
import { AdminVisualAssetsCard } from '../AdminVisualAssetsCard'
import { AdminFeedbackSubTab, AdminNotifTelegramSubTab } from '../AdminCommsSection'
import { AdminStockCreateModal, DeviceQrStickerModal } from '../AdminDeviceModals'
import { AdminDynamicContentTab } from '../AdminDynamicContentCard'
import { AppLockSubView, ChangelogSubView, RateFeedbackModal } from '../ProfileSubViews'
import { getAppLockConfig } from '../../utils/userPrefs'
import { VISUAL_ASSET_CATALOG, resolveVisualAsset } from '../../utils/mascotAssets'
import { buildQrMatrix } from '../../utils/qrMatrix'

describe('VoltKu Paket & Profil modal render guards', () => {
  it('renders PlanUpgradeModal without ReferenceError when opened from banner or profile (free plan)', () => {
    const html = renderToStaticMarkup(
      <PlanUpgradeModal
        isOpen
        onClose={() => {}}
        currentUser={{
          id: 1,
          name: 'Bu Ulis',
          email: 'warung@example.com',
          plan: { is_pro: false, plan_name: 'VoltKu Gratis', limits: { max_devices: 1, history_days: 3 } },
        }}
          appConfig={{
            app_name: 'VoltKu',
            plans: {
              upgrade_instructions: 'Transfer lalu upload bukti bayar.',
              free: { name: 'VoltKu Gratis', max_devices: 1, history_days: 3 },
              pro: { name: 'VoltKu Pro', price_monthly_rp: 30000, price_yearly_rp: 300000 },
              items: [
                {
                  slug: 'free',
                  name: 'VoltKu Gratis',
                  is_default_free: true,
                  max_devices: 1,
                  history_days: 3,
                },
                {
                  slug: 'pro',
                  name: 'VoltKu Pro',
                  is_recommended: true,
                  price_monthly_rp: 30000,
                  price_yearly_rp: 300000,
                  effective_monthly_price_rp: 30000,
                  effective_yearly_price_rp: 300000,
                  max_devices: 10,
                  history_days: 90,
                  forecast_enabled: true,
                  export_enabled: true,
                  anomaly_advanced: true,
                  features: ['Hingga 10 panel aktif', 'Prioritas WhatsApp'],
                },
              ],
            },
          }}
          token="test-token"
      />
    )
    expect(html).toContain('Pilih Paket VoltKu')
    expect(html).toContain('VoltKu Gratis')
    expect(html).toContain('VoltKu Pro')
    expect(html).toContain('Prioritas WhatsApp')
    expect((html.match(/Hingga 10 panel aktif/g) || []).length).toBe(1)
  })

  it('renders PlanUpgradeModal cleanly with empty appConfig and active pro user', () => {
    const html = renderToStaticMarkup(
      <PlanUpgradeModal
        isOpen
        onClose={() => {}}
        currentUser={{
          id: 2,
          name: 'Pemilik Pro',
          plan: {
            is_pro: true,
            plan_name: 'VoltKu Pro',
            usage: { device_count: 2 },
            limits: { max_devices: 10, history_days: 90, forecast_enabled: true, export_enabled: true },
          },
        }}
        appConfig={{}}
        token="test-token"
      />
    )
    expect(html).toContain('VoltKu Pro Aktif')
  })

  it('renders PlanUpgradeModal cleanly for awaiting_payment and verifying orders', () => {
    const htmlAwait = renderToStaticMarkup(
      <PlanUpgradeModal
        isOpen
        onClose={() => {}}
        currentUser={{
          id: 3,
          name: 'Uji Order',
          plan: {
            is_pro: false,
            pending_upgrade: {
              id: 12,
              order_code: 'VK-20261127-0012',
              status: 'awaiting_payment',
              billing_cycle: 'monthly',
              amount_rp: 30000,
              payment_method_type: 'qris',
              payment_method_label: 'QRIS Toko',
            },
          },
        }}
        appConfig={{}}
        token="test-token"
      />
    )
    expect(htmlAwait).toContain('VK-20261127-0012')
  })

  it('renders ProfileModal cleanly with Upgrade CTA entry', () => {
    const html = renderToStaticMarkup(
      <ProfileModal
        isOpen
        onClose={() => {}}
        onOpenPlanModal={() => {}}
        currentUser={{
          id: 1,
          name: 'Bu Ulis',
          email: 'warung@example.com',
          plan: { is_pro: false, plan_name: 'VoltKu Gratis', limits: { max_devices: 1, history_days: 3 } },
        }}
        appConfig={{ app_name: 'VoltKu' }}
        token="test-token"
      />
    )
    expect(html).toContain('Bandingkan semua paket')
    expect(html).toContain('Upgrade')
  })

  it('renders SettingsView Tarif & Daya cleanly with WITA/WIT timezone labels and sync badge', () => {
    const html = renderToStaticMarkup(
      <SettingsView
        mode="global"
        isAuthenticated
        settings={{
          tariff_rp: '1444.70',
          power_limit_w: 2200,
          alert_cooldown_min: 30,
          extra_percent: 0,
          report_hour: 21,
          report_timezone: 'Asia/Makassar',
          report_enabled: true,
        }}
        appConfig={{ app_name: 'VoltKu' }}
      />
    )
    expect(html).toContain('Zona Waktu Daerah (WIB / WITA / WIT)')
    expect(html).toContain('Jam Kirim Rekap Harian (WITA)')
    expect(html).toContain('settings-tz-pill selected')
    expect(html).toContain('21:00')
    expect(html).not.toContain('Mode Gelap')
  })

  it('renders HeroBannerCarousel with cloned head/tail slides starting cleanly on real slide 1', () => {
    const html = renderToStaticMarkup(
      <HeroBannerCarousel isAuthenticated currentUser={{ id: 1, plan: { is_pro: false } }} />
    )
    const tabCount = (html.match(/role="tab"/g) || []).length
    const slideBtnCount = (html.match(/class="ewl-hero-slide /g) || []).length
    const cloneCount = (html.match(/aria-hidden="true"/g) || []).length
    expect(tabCount).toBe(5)
    expect(slideBtnCount).toBe(7)
    expect(cloneCount).toBeGreaterThanOrEqual(2)
    expect(html).toContain('translate3d(calc(-100% + 0px), 0, 0)')
  })

  it('derives synced PIN status from currentUser.app_lock and renders AppLockSubView active', () => {
    const syncedCfg = getAppLockConfig({
      id: 42,
      app_lock: { pin_enabled: true, pin_updated_at: 1730000000, locked_until: null },
    })
    expect(syncedCfg.enabled).toBe(true)
    expect(syncedCfg.syncedWithAccount).toBe(true)

    const html = renderToStaticMarkup(
      <AppLockSubView
        currentUser={{
          id: 42,
          name: 'Dede',
          email: 'dede@voltku.id',
          app_lock: { pin_enabled: true, pin_updated_at: 1730000000 },
        }}
        token="tok"
      />
    )
    expect(html).toContain('Aktif · PIN 6 Digit tersinkron ke semua perangkat')
    expect(html).toContain('Ubah PIN 6 Digit')
  })

  it('respects Admin-configured hero_banners, filters hidden/audience slides, and hides carousel when empty', () => {
    const customHtml = renderToStaticMarkup(
      <HeroBannerCarousel
        isAuthenticated
        currentUser={{ id: 1, plan: { is_pro: false } }}
        appConfig={{
          hero_banners: [
            {
              id: 'promo-1',
              badge: 'CUSTOM ADMIN',
              title: 'Banner Kustom Pertama',
              subtitle: 'Tampil untuk pengguna gratis',
              cta: 'Buka',
              tone: 'is-cobalt',
              icon: 'sparkles',
              action_type: 'upgrade_plan',
              audience: 'free_only',
              enabled: true,
            },
            {
              id: 'pro-secret',
              badge: 'PRO',
              title: 'Khusus Pro Saja',
              subtitle: 'Tidak tampil untuk gratis',
              cta: 'Cek',
              tone: 'is-emerald',
              icon: 'crown',
              action_type: 'open_alerts',
              audience: 'pro_only',
              enabled: true,
            },
            {
              id: 'disabled-banner',
              badge: 'MATI',
              title: 'Disembunyikan Admin',
              subtitle: 'Harus tersaring',
              cta: 'Lihat',
              tone: 'is-indigo',
              icon: 'zap',
              action_type: 'none',
              audience: 'all',
              enabled: false,
            },
          ],
        }}
      />
    )
    expect(customHtml).toContain('Banner Kustom Pertama')
    expect(customHtml).not.toContain('Khusus Pro Saja')
    expect(customHtml).not.toContain('Disembunyikan Admin')

    const emptyHtml = renderToStaticMarkup(
      <HeroBannerCarousel
        isAuthenticated
        currentUser={{ id: 1, plan: { is_pro: false } }}
        appConfig={{ hero_banners: [] }}
      />
    )
    expect(emptyHtml).toBe('')
  })

  it('renders AdminHeroBannersCard with edit/delete items and empty state', () => {
    const populatedHtml = renderToStaticMarkup(
      <AdminHeroBannersCard
        banners={[
          {
            id: 'b1',
            badge: 'INFO',
            title: 'Banner Uji Admin',
            subtitle: 'Subjudul uji',
            cta: 'Buka',
            tone: 'is-cobalt',
            icon: 'sparkles',
            action_type: 'usage_guide',
            audience: 'all',
            enabled: true,
          },
        ]}
      />
    )
    expect(populatedHtml).toContain('Kontrol Hero Banner Beranda')
    expect(populatedHtml).toContain('Banner Uji Admin')
    expect(populatedHtml).toContain('Pulihkan Bawaan')
    expect(populatedHtml).toContain('Tambah Banner')

    const emptyAdminHtml = renderToStaticMarkup(<AdminHeroBannersCard banners={[]} />)
    expect(emptyAdminHtml).toContain('Tidak ada hero banner aktif')
    expect(emptyAdminHtml).toContain('Tambah Banner Pertama')
  })

  it('renders AdminPanel with two-tier clean navbar and subnav tabs', () => {
    const html = renderToStaticMarkup(
      <AdminPanel token="admin-tok" theme="light" onToggleTheme={() => {}} onLogout={() => {}} />
    )
    expect(html).toContain('admin-topbar-row')
    expect(html).toContain('admin-subnav-bar')
    expect(html).toContain('admin-nav-tab active')
    expect(html).toContain('Web User')
  })

  it('renders VoltKu mascot visuals across AiChatWidget, AnomaliesList, OnboardingTour, and PlanUpgradeModal', () => {
    const chatHtml = renderToStaticMarkup(<AiChatWidget token="tok" />)
    expect(chatHtml).toContain('ai-chat-fab-avatar')
    expect(chatHtml).toContain('Tanya VoltKu')

    const healthyHtml = renderToStaticMarkup(<AnomaliesList anomalies={[]} />)
    expect(healthyHtml).toContain('healthy-mascot-wrap')

    const alertHtml = renderToStaticMarkup(
      <AnomaliesList
        anomalies={[{ id: 1, ts: 1730000000, type: 'power_limit', severity: 'critical', message: 'Overload' }]}
      />
    )
    expect(alertHtml).toContain('anomaly-alert-hero')

    const tourHtml = renderToStaticMarkup(<OnboardingTour isOpen />)
    expect(tourHtml).toContain('guide-illus-mascot')
  })

  it('uses distinct icons for Peringatan nav (ShieldAlert) and Kotak Masuk Notifikasi (Bell)', () => {
    const html = renderToStaticMarkup(
      <Header
        activeTab="home"
        onTabChange={() => {}}
        isAuthenticated
        currentUser={{ id: 1, name: 'Uji', email: 'u@example.com' }}
      />
    )
    expect(html).toContain('lucide-shield-alert')
    expect(html).toContain('lucide-bell')
    expect(html).toContain('header-brand-btn')
    expect(html).toContain('Kembali ke Beranda')
  })

  it('renders UsageGuideModal cleanly with mascot card and inline kbd pills', () => {
    const html = renderToStaticMarkup(<UsageGuideModal isOpen onClose={() => {}} />)
    expect(html).toContain('Cara Pemakaian VoltKu')
    expect(html).toContain('ug-hero-guide-card')
    expect(html).toContain('ug-kbd-pill')
    expect(html).toContain('5 Langkah Menghubungkan Panel')
  })

  it('supports Admin visual assets CRUD catalog, custom URL resolution, and hiding mascots', () => {
    expect(VISUAL_ASSET_CATALOG).toHaveLength(7)

    // Default resolution falls back to bundled asset string
    const defaultBanner = resolveVisualAsset({}, 'pro_banner')
    expect(typeof defaultBanner).toBe('string')
    expect(defaultBanner.length).toBeGreaterThan(0)

    // Custom URL overrides default
    const customBanner = resolveVisualAsset(
      { visual_assets: { pro_banner: { enabled: true, is_custom: true, url: '/api/public/visual-assets/pro_banner?v=12' } } },
      'pro_banner'
    )
    expect(customBanner).toContain('/api/public/visual-assets/pro_banner?v=12')

    // Disabled slot returns null even if custom URL is set
    expect(
      resolveVisualAsset(
        { visual_assets: { pro_banner: { enabled: false, is_custom: true, url: '/api/public/visual-assets/pro_banner?v=12' } } },
        'pro_banner'
      )
    ).toBeNull()

    // AdminVisualAssetsCard renders all 7 slots with status badges & actions
    const adminCardHtml = renderToStaticMarkup(
      <AdminVisualAssetsCard
        visualAssets={{
          chatbot_avatar: { enabled: true, is_custom: true, url: '/api/public/visual-assets/chatbot_avatar?v=5' },
          pro_banner: { enabled: false, is_custom: false, url: null },
        }}
      />
    )
    expect(adminCardHtml).toContain('Kontrol Gambar &amp; Maskot Aplikasi')
    expect(adminCardHtml).toContain('Ganti Gambar')
    expect(adminCardHtml).toContain('Kustom')
    expect(adminCardHtml).toContain('Disembunyikan')
    expect(adminCardHtml).toContain('Pulihkan Bawaan')

    // Disabling mascots cleanly hides image stages across customer components
    const hiddenConfig = {
      visual_assets: {
        chatbot_avatar: { enabled: false, is_custom: false, url: null },
        anomaly_healthy: { enabled: false, is_custom: false, url: null },
        onboarding_welcome: { enabled: false, is_custom: false, url: null },
        pro_banner: { enabled: false, is_custom: false, url: null },
      },
    }
    const hiddenChatHtml = renderToStaticMarkup(<AiChatWidget token="tok" appConfig={hiddenConfig} />)
    expect(hiddenChatHtml).not.toContain('ai-chat-fab-avatar')

    const hiddenHealthyHtml = renderToStaticMarkup(
      <AnomaliesList anomalies={[]} appConfig={hiddenConfig} />
    )
    expect(hiddenHealthyHtml).not.toContain('healthy-mascot-wrap')

    const hiddenTourHtml = renderToStaticMarkup(<OnboardingTour isOpen appConfig={hiddenConfig} />)
    expect(hiddenTourHtml).not.toContain('guide-illus-stage')

    const hiddenPlanHtml = renderToStaticMarkup(
      <PlanUpgradeModal
        isOpen
        onClose={() => {}}
        currentUser={{ id: 1, name: 'Uji', email: 'u@e.id', plan: { is_pro: false } }}
        appConfig={hiddenConfig}
      />
    )
    expect(hiddenPlanHtml).not.toContain('plan-pro-showcase')
  })

  it('renders Stage 1 Admin Comms sub-tabs (Feedback & Broadcast/Telegram) and RateFeedbackModal cleanly', () => {
    const fbTabHtml = renderToStaticMarkup(<AdminFeedbackSubTab token="adm-tok" />)
    expect(fbTabHtml).toContain('Daftar Ulasan, Saran &amp; Laporan Bug Pelanggan')
    expect(fbTabHtml).toContain('Total Masukan')

    const commsHtml = renderToStaticMarkup(
      <AdminNotifTelegramSubTab
        token="adm-tok"
        users={[{ id: 1, name: 'Bu Ulis', email: 'bu@voltku.id', is_active: true }]}
      />
    )
    expect(commsHtml).toContain('Kirim Broadcast Notifikasi Pelanggan')
    expect(commsHtml).toContain('Allowlist Penerima &amp; Operator Bot Telegram')
    expect(commsHtml).toContain('Tambah Chat ID')

    const rateHtml = renderToStaticMarkup(
      <RateFeedbackModal isOpen onClose={() => {}} token="usr-tok" appName="VoltKu" />
    )
    expect(rateHtml).toContain('Ulasan')
    expect(rateHtml).toContain('Lapor Bug')
    expect(rateHtml).toContain('Usul Fitur')
    expect(rateHtml).toContain('Kirim Nilai')
  })

  it('generates valid QR sticker matrices and supports Stage 2 Dynamic Content CRUD & overrides', () => {
    const mx = buildQrMatrix('VOLTKU:VK-STOK-01')
    expect(mx).toBeTruthy()
    expect(mx.size).toBeGreaterThanOrEqual(21)

    const qrModalHtml = renderToStaticMarkup(
      <DeviceQrStickerModal
        device={{ id: 'VK-STOK-01', name: 'Panel Uji', mcb_watt: 2200 }}
        appName="VoltKu"
        onClose={() => {}}
      />
    )
    expect(qrModalHtml).toContain('Stiker QR Pairing Unit')
    expect(qrModalHtml).toContain('VK-STOK-01')
    expect(qrModalHtml).toContain('Unduh Stiker PNG')

    const stockModalHtml = renderToStaticMarkup(
      <AdminStockCreateModal isOpen users={[]} token="adm-tok" onClose={() => {}} />
    )
    expect(stockModalHtml).toContain('Tambah Stok Unit Panel')
    expect(stockModalHtml).toContain('Batch Banyak Unit')

    const customAppConfig = {
      ai_quick_prompts: ['Prompt Uji Admin 1'],
      pln_tariffs: [
        { id: 't-custom', category: 'rumah', group: 'Rumah', label: 'Tarif Kustom', tariff_rp: '1555.00' },
      ],
      app_release: {
        version: 'v2.9.9',
        apk_download_url: 'https://voltku.synemax.web.id/VoltKu.apk',
        release_notes: 'Catatan rilis uji.',
        changelog: [{ version: 'v2.9.9', date: '27 Nov 2026', badge: 'Uji', items: ['Item rilis'] }],
      },
      usage_guide: {
        pairing_intro_title: 'Intro Kustom Admin',
        pairing_intro_desc: 'Deskripsi intro kustom.',
        usage_intro_title: 'Pantau Kustom',
        usage_intro_desc: 'Deskripsi pantau kustom.',
        pairing_steps: [{ step: 1, text: 'Langkah 1 dari Admin' }],
        usage_cards: [{ title: 'Kartu Uji', desc: 'Deskripsi kartu uji' }],
      },
    }

    const dynAdminHtml = renderToStaticMarkup(
      <AdminDynamicContentTab appSettings={customAppConfig} onPersistFields={() => {}} />
    )
    expect(dynAdminHtml).toContain('Info Versi APK, Tautan Update')
    expect(dynAdminHtml).toContain('Preset Golongan Tarif PLN (1 Preset)')
    expect(dynAdminHtml).toContain('Pertanyaan Cepat Asisten AI (1/8)')

    const guideHtml = renderToStaticMarkup(
      <UsageGuideModal isOpen appConfig={customAppConfig} onClose={() => {}} />
    )
    expect(guideHtml).toContain('Intro Kustom Admin')
    expect(guideHtml).toContain('Langkah 1 dari Admin')

    const changelogHtml = renderToStaticMarkup(<ChangelogSubView appConfig={customAppConfig} />)
    expect(changelogHtml).toContain('Unduh APK Android (v2.9.9)')
    expect(changelogHtml).toContain('Item rilis')

    const settingsHtml = renderToStaticMarkup(
      <SettingsView mode="global" settings={{}} appConfig={customAppConfig} isAuthenticated />
    )
    expect(settingsHtml).toContain('Golongan Tarif PLN (1 Pilihan)')
  })
})

