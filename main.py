"""
main.py — CLI test arayüzü.
3 senaryoyu sırayla çalıştırır:
  1. Normal istek — başarılı yanıt, log yazıldı
  2. Rate limit testi — aynı kullanıcıdan 25 hızlı istek, 429 görülüyor mu
  3. Bütçe testi — team_beta düşük limitli, aşımda red görülüyor mu
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from src.gateway import Gateway

SEPARATOR = "=" * 65


def section(title: str):
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def main():
    print(SEPARATOR)
    print("  🚀  LLM GATEWAY — Test Senaryoları")
    print(SEPARATOR)

    gw = Gateway()

    # ──────────────────────────────────────────────────────────────────
    # SENARYO 1: Normal istek
    # ──────────────────────────────────────────────────────────────────
    section("SENARYO 1: Normal İstek")
    print("→ Kullanıcı: user_normal | Ekip: team_alpha")
    print("→ Prompt: 'Yapay zekanın 3 temel uygulama alanını listele.'")

    result = gw.complete(
        prompt="Yapay zekanın 3 temel uygulama alanını listele.",
        user_id="user_normal",
        team_id="team_alpha",
        ip="10.0.0.1",
    )

    if result.success:
        print(f"\n✅  Yanıt alındı!")
        print(f"   Provider  : {result.log_record.get('provider')}")
        print(f"   Model     : {result.log_record.get('model')}")
        print(f"   Tokens    : {result.log_record.get('total_tokens')} "
              f"(in={result.log_record.get('input_tokens')}, "
              f"out={result.log_record.get('output_tokens')})")
        print(f"   Maliyet   : ${result.log_record.get('cost_usd', 0):.6f}")
        print(f"   Gecikme   : {result.log_record.get('latency_ms', 0):.0f}ms")
        print(f"\n   Yanıt önizleme: {result.text[:200]}...")
    else:
        print(f"❌  Hata [{result.status_code}]: {result.error}")

    # Bütçe durumu
    budget_status = gw.get_budget_status("team_alpha")
    print(f"\n   Bütçe Durumu (team_alpha):")
    print(f"   Limit: ${budget_status.get('budget_usd', 0):.4f} | "
          f"Harcanan: ${budget_status.get('spent_usd', 0):.6f} | "
          f"Kalan: ${budget_status.get('remaining_usd', 0):.6f} | "
          f"Kullanım: %{budget_status.get('usage_pct', 0):.2f}")

    # ──────────────────────────────────────────────────────────────────
    # SENARYO 2: Rate limit testi
    # ──────────────────────────────────────────────────────────────────
    section("SENARYO 2: Rate Limit Testi (25 hızlı istek)")
    print("→ Kullanıcı: user_spammer | Limit: 20 istek/dk")
    print("→ 429 hatası 21. istekten itibaren bekleniyor...\n")

    from src.rate_limiter import RateLimiter, RateLimitExceeded

    # ⚠️ Tek bir instance üzerinden 25 istek — sayaç birikir ve 429 tetiklenir
    test_limiter = RateLimiter(user_limit=20, ip_limit=100)

    success_count = 0
    rate_limited_count = 0

    for i in range(1, 26):
        try:
            test_limiter.check(user_id="user_spammer", ip="10.0.0.99")
            success_count += 1
            if i <= 3 or i == 20:
                print(f"   [{i:02d}/25] ✅ İzin verildi")
            elif i == 4:
                print(f"   [...] (istekler kabul ediliyor...)")
        except RateLimitExceeded as e:
            rate_limited_count += 1
            if rate_limited_count <= 3:
                print(f"   [{i:02d}/25] ❌ 429 Rate Limit — {str(e)[:80]}")
            elif rate_limited_count == 4:
                print(f"   [...] (sonraki istekler de 429 alıyor...)")

    print(f"\n   📊 Özet:")
    print(f"   ✅ Kabul edilen : {success_count}/25")
    print(f"   ❌ 429 Reddedilen: {rate_limited_count}/25")
    assert rate_limited_count == 5, f"Beklenen 5 red, gelen: {rate_limited_count}"
    print(f"   ✅ TEST BAŞARILI: 20 istek kabul edildi, {rate_limited_count} istek 429 ile reddedildi.")

    # ──────────────────────────────────────────────────────────────────
    # SENARYO 3: Bütçe testi
    # ──────────────────────────────────────────────────────────────────
    section("SENARYO 3: Bütçe Testi (team_beta — $0.001 limit)")
    print("→ Kullanıcı: user_beta | Ekip: team_beta")
    print("→ budgets.json'da team_beta limiti $0.001 olarak tanımlandı.")
    print("→ İlk çağrı bütçeyi tüketirse ikincisi reddedilmeli...\n")

    # Önce bütçeyi sıfırla (temiz test)
    from src.budget import BudgetManager
    bm = BudgetManager()
    bm.reset("team_beta")

    # team_beta ile gerçek API çağrısı yap (küçük prompt)
    r1 = gw.complete(
        prompt="Merhaba!",
        user_id="user_beta",
        team_id="team_beta",
        ip="10.0.0.2",
    )

    if r1.success:
        cost = r1.log_record.get("cost_usd", 0)
        print(f"   1. İstek → ✅ Başarılı | Maliyet: ${cost:.6f}")
    else:
        print(f"   1. İstek → ❌ {r1.status_code} {r1.error[:80]}")

    budget_after_1 = gw.get_budget_status("team_beta")
    print(f"   Bütçe: ${budget_after_1.get('spent_usd', 0):.6f} / "
          f"${budget_after_1.get('budget_usd', 0):.4f} "
          f"(Kalan: ${budget_after_1.get('remaining_usd', 0):.6f})")

    # Bütçeyi aşmak için spent'i manüel olarak limit üstüne çek
    import json
    budget_data_path = "data/budgets.json"
    with open(budget_data_path, "r", encoding="utf-8") as f:
        bd = json.load(f)
    bd["team_beta"]["spent_usd"] = bd["team_beta"]["budget_usd"] + 0.0001
    with open(budget_data_path, "w", encoding="utf-8") as f:
        json.dump(bd, f, indent=2)

    print(f"\n   (Bütçe manuel olarak aşıldı — test için)")

    r2 = gw.complete(
        prompt="Bu istek reddedilmeli!",
        user_id="user_beta",
        team_id="team_beta",
        ip="10.0.0.2",
    )

    if not r2.success and r2.status_code == 402:
        print(f"   2. İstek → ✅ DOĞRU! 402 Bütçe Aşımı ile reddedildi.")
        print(f"   Hata: {r2.error[:100]}")
    else:
        print(f"   2. İstek → ❌ BEKLENMEYEN SONUÇ: {r2.status_code} {r2.error}")

    # Bütçeyi geri sıfırla
    bm.reset("team_beta")

    # ──────────────────────────────────────────────────────────────────
    # ÖZET: Telemetry istatistikleri
    # ──────────────────────────────────────────────────────────────────
    section("📊 TELEMETRİ ÖZETİ")
    stats = gw.get_telemetry_stats()
    print(f"   Toplam İstek   : {stats.get('total_requests', 0)}")
    print(f"   Başarılı       : {stats.get('successful_requests', 0)}")
    print(f"   Başarısız      : {stats.get('failed_requests', 0)}")
    print(f"   Başarı Oranı   : %{stats.get('success_rate_pct', 0)}")
    print(f"   Toplam Maliyet : ${stats.get('total_cost_usd', 0):.6f}")
    print(f"   Ort. Gecikme   : {stats.get('avg_latency_ms', 0):.1f}ms")
    print(f"\n   📁 Detaylı loglar: logs/requests.jsonl\n")

    print(SEPARATOR)
    print("  ✅  Tüm senaryolar tamamlandı!")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
