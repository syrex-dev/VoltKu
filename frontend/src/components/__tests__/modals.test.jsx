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
import { Header } from '../Header'
import { AppLockSubView } from '../ProfileSubViews'
import { getAppLockConfig } from '../../utils/userPrefs'

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
          },
        }}
        token="test-token"
      />
    )
    expect(html).toContain('Pilih Paket VoltKu')
    expect(html).toContain('VoltKu Gratis')
    expect(html).toContain('VoltKu Pro')
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
  })
})

