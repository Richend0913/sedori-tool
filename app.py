"""
せどり価格差リサーチツール - Web UI (Streamlit)
"""
import streamlit as st
import pandas as pd
import re
import time
from difflib import SequenceMatcher

# ── ページ設定 ──
st.set_page_config(page_title="せどりリサーチ", page_icon="💰", layout="wide")

# ── スタイル ──
st.markdown("""
<style>
.profit-positive { color: #10b981; font-weight: bold; font-size: 1.2em; }
.profit-negative { color: #ef4444; font-weight: bold; }
.metric-card { background: #1e1e2e; padding: 16px; border-radius: 12px; text-align: center; }
.metric-value { font-size: 1.8em; font-weight: bold; color: #f0f0f0; }
.metric-label { font-size: 0.8em; color: #888; }
</style>
""", unsafe_allow_html=True)

# ── 手数料設定 ──
FEES = {
    "メルカリ": 0.10,
    "ヤフオク": 0.088,
    "ヤフオク(非プレミアム)": 0.10,
    "Amazon FBA": 0.15,
    "ラクマ": 0.06,
}
SHIPPING = {
    "ネコポス (A4/1kg以下)": 210,
    "ゆうパケット": 230,
    "宅急便コンパクト": 600,
    "宅急便 60サイズ": 930,
    "宅急便 80サイズ": 1150,
    "宅急便 100サイズ": 1390,
}
GENRES = {
    "ゲーム": ["Nintendo Switch ソフト", "PS5 ソフト", "ゲームコントローラー", "amiibo", "ゲーミングヘッドセット"],
    "コスメ": ["デパコス 限定", "SUQQU", "NARS チーク", "MAC リップ", "資生堂 限定"],
    "家電": ["ワイヤレスイヤホン", "モバイルバッテリー", "電動歯ブラシ", "ヘアアイロン", "加湿器"],
    "ホビー": ["ワンピース フィギュア", "ポケモンカード", "遊戯王 レア", "レゴ 限定", "ガンプラ"],
    "ファッション": ["ノースフェイス", "ナイキ スニーカー", "Supreme", "ユニクロ コラボ", "GU 完売"],
    "本・メディア": ["ビジネス書 ベストセラー", "漫画 全巻セット", "TOEIC 参考書", "絵本 セット", "DVD BOX"],
}

def similarity(a: str, b: str) -> float:
    """商品名の類似度(0-1)"""
    a = re.sub(r'[\s\u3000【】\[\]()（）]', '', a.lower())
    b = re.sub(r'[\s\u3000【】\[\]()（）]', '', b.lower())
    return SequenceMatcher(None, a, b).ratio()

def calc_profit(buy_price, sell_price, fee_rate, shipping, packing=50):
    fee = int(sell_price * fee_rate)
    total_cost = buy_price + fee + shipping + packing
    profit = sell_price - total_cost
    roi = (profit / buy_price * 100) if buy_price > 0 else 0
    return {"fee": fee, "total_cost": total_cost, "profit": profit, "roi": round(roi, 1)}

def scrape_amazon(keyword, limit=10):
    """Amazon検索"""
    from playwright.sync_api import sync_playwright
    results = []
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page.goto(f"https://www.amazon.co.jp/s?k={keyword}", timeout=15000)
        time.sleep(2)
        items = page.query_selector_all('[data-component-type="s-search-result"]')
        for item in items[:limit]:
            try:
                name = item.query_selector('h2 a span, h2 span')
                price = item.query_selector('.a-price-whole')
                img = item.query_selector('img.s-image')
                link = item.query_selector('h2 a')
                n = name.inner_text().strip()[:80] if name else ""
                p = int(re.sub(r'[^\d]', '', price.inner_text())) if price else 0
                u = link.get_attribute('href') if link else ""
                if u and not u.startswith('http'): u = f"https://www.amazon.co.jp{u}"
                im = img.get_attribute('src') if img else ""
                if n and p > 0:
                    results.append({"name": n, "price": p, "url": u, "image": im, "platform": "Amazon"})
            except: continue
        browser.close(); pw.stop()
    except Exception as e:
        st.warning(f"Amazon取得エラー: {e}")
    return results

def _launch_browser():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    return pw, browser, page

def _extract_prices(items, name_sel, price_sel, link_sel, img_sel, base_url, platform, limit):
    results = []
    for item in items[:limit]:
        try:
            name_el = item.query_selector(name_sel)
            price_el = item.query_selector(price_sel)
            link_el = item.query_selector(link_sel) if link_sel else item
            img_el = item.query_selector(img_sel) if img_sel else None
            n = name_el.inner_text().strip()[:80] if name_el else ""
            pt = price_el.inner_text().strip() if price_el else ""
            p = int(re.sub(r'[^\d]', '', pt.split('円')[0].split('～')[0])) if pt else 0
            u = ""
            if link_el:
                u = link_el.get_attribute('href') or ""
                if u and not u.startswith('http'): u = f"{base_url}{u}"
            im = img_el.get_attribute('src') if img_el else ""
            if n and p > 0:
                results.append({"name": n, "price": p, "url": u, "image": im, "platform": platform})
        except: continue
    return results

def scrape_mercari(keyword, limit=10):
    """メルカリ売却済み検索"""
    pw, browser, page = _launch_browser()
    results = []
    try:
        page.goto(f"https://jp.mercari.com/search?keyword={keyword}&status=sold_out&order=desc&sort=created_time", timeout=15000)
        time.sleep(4)
        # Use item-cell elements (more reliable)
        items = page.query_selector_all('[data-testid="item-cell"]')
        for item in items[:limit]:
            try:
                # aria-label contains "商品名の画像 売り切れ 価格円"
                aria = item.query_selector('[aria-label]')
                aria_text = aria.get_attribute('aria-label') if aria else ""
                # Extract from aria: "商品名の画像 売り切れ ○○円"
                name = ""
                price = 0
                if aria_text:
                    # Remove "の画像" suffix and parse
                    parts = aria_text.replace('の画像', '').split(' 売り切れ ')
                    if len(parts) >= 2:
                        name = parts[0].strip()[:80]
                        price_text = parts[1].strip()
                        price = int(re.sub(r'[^\d]', '', price_text.replace(',', '')))

                # Fallback: use spans
                if not name:
                    spans = item.query_selector_all('span')
                    for s in spans:
                        txt = s.inner_text().strip()
                        if txt and '¥' not in txt and len(txt) > 5:
                            name = txt[:80]
                            break
                if not price:
                    spans = item.query_selector_all('span')
                    for s in spans:
                        txt = s.inner_text().strip()
                        if txt and re.match(r'^[\d,]+$', txt) and int(txt.replace(',','')) > 0:
                            price = int(txt.replace(',', ''))
                            break

                img_el = item.query_selector('img')
                im = img_el.get_attribute('src') if img_el else ""
                # Get item ID from aria element
                item_id = aria.get_attribute('id') if aria else ""
                url = f"https://jp.mercari.com/item/{item_id}" if item_id else ""

                if name and price > 0:
                    results.append({"name": name, "price": price, "url": url, "image": im, "platform": "メルカリ(売却済)"})
            except: continue
    except Exception as e:
        st.warning(f"メルカリ取得エラー: {e}")
    finally:
        browser.close(); pw.stop()
    return results

def scrape_rakuten(keyword, limit=10):
    """楽天商品検索"""
    pw, browser, page = _launch_browser()
    results = []
    try:
        page.goto(f"https://search.rakuten.co.jp/search/mall/{keyword}/", timeout=15000)
        time.sleep(3)
        items = page.query_selector_all('.searchresultitem, [class*="dui-card"], div[class*="Product"]')
        for item in items[:limit]:
            try:
                name_el = item.query_selector('.content.title a, h2 a, a[class*="title"]')
                price_el = item.query_selector('.important, [class*="price"]')
                img_el = item.query_selector('img')
                n = name_el.inner_text().strip()[:80] if name_el else ""
                pt = price_el.inner_text().strip() if price_el else ""
                p = int(re.sub(r'[^\d]', '', pt.split('円')[0])) if pt else 0
                u = name_el.get_attribute('href') if name_el else ""
                im = img_el.get_attribute('src') if img_el else ""
                if n and p > 0:
                    results.append({"name": n, "price": p, "url": u, "image": im, "platform": "楽天"})
            except: continue
    except Exception as e:
        st.warning(f"楽天取得エラー: {e}")
    finally:
        browser.close(); pw.stop()
    return results

def scrape_yahoo_auction(keyword, limit=10):
    """ヤフオク落札相場"""
    pw, browser, page = _launch_browser()
    results = []
    try:
        page.goto(f"https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={keyword}&b=1&n=20", timeout=15000)
        time.sleep(4)
        # Use img alt text for product names + parent link for URLs
        imgs = page.query_selector_all('img[alt]')
        seen = set()
        for img in imgs:
            if len(results) >= limit: break
            try:
                alt = img.get_attribute('alt') or ""
                if len(alt) < 5: continue
                src = img.get_attribute('src') or ""
                # Get parent auction link and price
                info = img.evaluate("""el => {
                    let link = el.closest('a');
                    let href = link ? link.href : '';
                    if (!href.includes('/auction/')) return null;
                    let li = el.closest('li');
                    let text = li ? li.innerText : '';
                    return {href: href, text: text};
                }""")
                if not info or not info.get('href'): continue
                href = info['href']
                if href in seen: continue
                seen.add(href)
                # Extract price from li text
                text = info.get('text', '')
                price_match = re.findall(r'([\d,]+)円', text)
                price = int(price_match[0].replace(',', '')) if price_match else 0
                if alt and price > 0:
                    results.append({"name": alt[:80], "price": price, "url": href, "image": src, "platform": "ヤフオク(落札)"})
            except: continue
    except Exception as e:
        st.warning(f"ヤフオク取得エラー: {e}")
    finally:
        browser.close(); pw.stop()
    return results

def scrape_yahoo_shopping(keyword, limit=10):
    """ヤフーショッピング商品検索"""
    pw, browser, page = _launch_browser()
    results = []
    try:
        page.goto(f"https://shopping.yahoo.co.jp/search?p={keyword}", timeout=15000)
        time.sleep(3)
        items = page.query_selector_all('[class*="ProductItem"], [class*="mdSearchResult"]')
        for item in items[:limit]:
            try:
                name_el = item.query_selector('a[class*="title"], h3 a, a')
                price_el = item.query_selector('[class*="price"], span[class*="Price"]')
                img_el = item.query_selector('img')
                n = name_el.inner_text().strip()[:80] if name_el else ""
                pt = price_el.inner_text().strip() if price_el else ""
                p = int(re.sub(r'[^\d]', '', pt.split('円')[0])) if pt else 0
                u = name_el.get_attribute('href') if name_el else ""
                im = img_el.get_attribute('src') if img_el else ""
                if n and p > 0:
                    results.append({"name": n, "price": p, "url": u, "image": im, "platform": "Yahoo!ショッピング"})
            except: continue
    except Exception as e:
        st.warning(f"Yahoo!ショッピング取得エラー: {e}")
    finally:
        browser.close(); pw.stop()
    return results

# ── メインUI ──
st.title("💰 せどり価格差リサーチツール")
st.caption("Amazon/楽天で仕入れ → メルカリ/ヤフオクで販売。利益が出る商品を自動検出。")

tab1, tab2, tab3 = st.tabs(["🔍 キーワード検索", "📁 ジャンル一括検索", "🧮 利益計算機"])

with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        keyword = st.text_input("検索キーワード", placeholder="例: ワイヤレスイヤホン")
    with col2:
        min_profit = st.number_input("最低利益(円)", value=500, step=100)

    col_a, col_b = st.columns(2)
    with col_a:
        buy_sources = st.multiselect("仕入れ先", ["Amazon", "楽天", "Yahoo!ショッピング"], default=["Amazon", "楽天"])
    with col_b:
        sell_sources = st.multiselect("相場参照先", ["メルカリ", "ヤフオク"], default=["メルカリ", "ヤフオク"])

    sell_platform = st.selectbox("販売先（手数料計算用）", list(FEES.keys()), index=0)
    ship_type = st.selectbox("送料", list(SHIPPING.keys()), index=0)

    if st.button("🔍 リサーチ開始", type="primary", use_container_width=True):
        if not keyword:
            st.error("キーワードを入力してください")
        else:
            # 仕入れ先スクレイピング
            buy_items = []
            if "Amazon" in buy_sources:
                with st.spinner("Amazon検索中..."):
                    buy_items.extend(scrape_amazon(keyword, 8))
            if "楽天" in buy_sources:
                with st.spinner("楽天検索中..."):
                    buy_items.extend(scrape_rakuten(keyword, 8))
            if "Yahoo!ショッピング" in buy_sources:
                with st.spinner("Yahoo!ショッピング検索中..."):
                    buy_items.extend(scrape_yahoo_shopping(keyword, 8))

            # 相場参照先スクレイピング
            sell_items = []
            if "メルカリ" in sell_sources:
                with st.spinner("メルカリ相場検索中..."):
                    sell_items.extend(scrape_mercari(keyword, 15))
            if "ヤフオク" in sell_sources:
                with st.spinner("ヤフオク落札相場検索中..."):
                    sell_items.extend(scrape_yahoo_auction(keyword, 15))

            if not buy_items:
                st.warning("仕入れ先の商品が取得できませんでした")
            elif not sell_items:
                st.warning("販売相場が取得できませんでした")
            else:
                # 相場中央値
                s_prices = sorted([s["price"] for s in sell_items if s["price"] > 0])
                s_median = s_prices[len(s_prices)//2] if s_prices else 0

                buy_summary = ", ".join([f"{src}: {sum(1 for b in buy_items if b['platform']==src)}件" for src in set(b['platform'] for b in buy_items)])
                sell_summary = ", ".join([f"{src}: {sum(1 for s in sell_items if s['platform']==src)}件" for src in set(s['platform'] for s in sell_items)])
                st.success(f"仕入れ: {buy_summary} / 相場: {sell_summary} (中央値: {s_median:,}円)")

                mercari_items = sell_items  # 互換性のため
                m_median = s_median

                # 利益計算
                fee_rate = FEES[sell_platform]
                ship_cost = SHIPPING[ship_type]
                results = []

                for a in amazon_items:
                    # 商品一致: matcher.pyで正確な一致判定
                    from matcher import is_same_product
                    best_match = None
                    best_conf = 0
                    best_reason = ""
                    for m in mercari_items:
                        is_match, conf, reason = is_same_product(a["name"], m["name"])
                        if conf > best_conf:
                            best_conf = conf
                            best_match = m
                            best_reason = reason

                    sell_price = best_match["price"] if best_match and best_conf > 0.6 else m_median
                    match_name = best_match["name"] if best_match and best_conf > 0.6 else f"相場中央値"
                    match_score = f"{best_conf*100:.0f}% {best_reason}" if best_match else "-"

                    r = calc_profit(a["price"], sell_price, fee_rate, ship_cost)

                    results.append({
                        "商品名": a["name"][:50],
                        "仕入れ値": a["price"],
                        "販売予想": sell_price,
                        "一致度": match_score,
                        "手数料": r["fee"],
                        "送料": ship_cost,
                        "純利益": r["profit"],
                        "ROI": f"{r['roi']}%",
                        "仕入れURL": a["url"],
                        "画像": a.get("image", ""),
                    })

                # フィルタリング
                df = pd.DataFrame(results)
                profitable = df[df["純利益"] >= min_profit].sort_values("純利益", ascending=False)

                # メトリクス
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("検索結果", f"{len(amazon_items)}件")
                c2.metric("利益商品", f"{len(profitable)}件")
                c3.metric("最大利益", f"{profitable['純利益'].max():,}円" if len(profitable) > 0 else "0円")
                c4.metric("平均ROI", f"{profitable['ROI'].str.replace('%','').astype(float).mean():.0f}%" if len(profitable) > 0 else "0%")

                if len(profitable) > 0:
                    st.subheader(f"利益商品 ({len(profitable)}件)")
                    for _, row in profitable.iterrows():
                        with st.container():
                            cols = st.columns([1, 3, 1, 1, 1])
                            if row["画像"]:
                                cols[0].image(row["画像"], width=80)
                            cols[1].write(f"**{row['商品名']}**")
                            cols[1].caption(f"一致度: {row['一致度']}")
                            cols[2].metric("仕入れ", f"¥{row['仕入れ値']:,}")
                            cols[3].metric("販売予想", f"¥{row['販売予想']:,}")
                            profit_color = "normal" if row["純利益"] > 0 else "inverse"
                            cols[4].metric("純利益", f"¥{row['純利益']:,}", delta=f"ROI {row['ROI']}", delta_color=profit_color)
                            st.divider()

                    # CSV出力
                    csv_data = profitable.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 CSVダウンロード", csv_data, "sedori_results.csv", "text/csv")
                else:
                    st.info(f"利益{min_profit}円以上の商品は見つかりませんでした")

with tab2:
    genre = st.selectbox("ジャンルを選択", list(GENRES.keys()))
    st.caption(f"キーワード: {', '.join(GENRES[genre])}")
    if st.button("📁 ジャンル一括リサーチ", type="primary"):
        st.info("ジャンル一括検索は時間がかかります（各キーワード約15秒）")
        all_results = []
        progress = st.progress(0)
        keywords = GENRES[genre]
        for i, kw in enumerate(keywords):
            st.write(f"検索中: {kw}")
            with st.spinner(f"{kw} リサーチ中..."):
                amazon = scrape_amazon(kw, 5)
                mercari = scrape_mercari(kw, 10)
                if amazon and mercari:
                    m_prices = sorted([m["price"] for m in mercari if m["price"]>0])
                    m_med = m_prices[len(m_prices)//2] if m_prices else 0
                    for a in amazon:
                        r = calc_profit(a["price"], m_med, 0.10, 210)
                        if r["profit"] >= 500:
                            all_results.append({
                                "キーワード": kw,
                                "商品名": a["name"][:40],
                                "仕入れ値": a["price"],
                                "販売予想": m_med,
                                "純利益": r["profit"],
                                "ROI": f"{r['roi']}%",
                            })
            progress.progress((i+1)/len(keywords))
            time.sleep(1)

        if all_results:
            df = pd.DataFrame(all_results).sort_values("純利益", ascending=False)
            st.success(f"{len(all_results)}件の利益商品が見つかりました！")
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 CSV", csv, f"sedori_{genre}.csv", "text/csv")
        else:
            st.warning("利益商品が見つかりませんでした")

with tab3:
    st.subheader("利益計算機")
    c1, c2 = st.columns(2)
    with c1:
        buy_price = st.number_input("仕入れ値（円）", value=1000, step=100)
        sell_price = st.number_input("販売予定価格（円）", value=3000, step=100)
    with c2:
        platform = st.selectbox("販売先プラットフォーム", list(FEES.keys()), key="calc_platform")
        shipping = st.selectbox("送料", list(SHIPPING.keys()), key="calc_ship")

    if st.button("計算する", use_container_width=True):
        r = calc_profit(buy_price, sell_price, FEES[platform], SHIPPING[shipping])
        c1, c2, c3 = st.columns(3)
        c1.metric("総コスト", f"¥{r['total_cost']:,}")
        color = "normal" if r["profit"] > 0 else "inverse"
        c2.metric("純利益", f"¥{r['profit']:,}", delta_color=color)
        c3.metric("ROI", f"{r['roi']}%")

        st.write("---")
        st.write(f"仕入れ値: ¥{buy_price:,}")
        st.write(f"販売手数料 ({FEES[platform]*100:.1f}%): ¥{r['fee']:,}")
        st.write(f"送料: ¥{SHIPPING[shipping]:,}")
        st.write(f"梱包費: ¥50")
        st.write(f"**純利益: ¥{r['profit']:,}**")

# フッター
st.divider()
st.caption("せどり価格差リサーチツール v1.0 | データはリアルタイム取得")
