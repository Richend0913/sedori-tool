"""せどりリサーチツール - デモ版（Streamlit Cloud対応）"""
import streamlit as st
import pandas as pd
import re
import random
from difflib import SequenceMatcher

st.set_page_config(page_title="せどりリサーチ", page_icon="💰", layout="wide")

st.markdown("""<style>
.stMetric { background: #1a1a2e; padding: 12px; border-radius: 10px; }
</style>""", unsafe_allow_html=True)

FEES = {"メルカリ": 0.10, "ヤフオク": 0.088, "ヤフオク(非プレミアム)": 0.10, "Amazon FBA": 0.15, "ラクマ": 0.06}
SHIPPING = {"ネコポス (A4/1kg以下)": 210, "ゆうパケット": 230, "宅急便コンパクト": 600, "宅急便 60サイズ": 930, "宅急便 80サイズ": 1150}

DEMO_DATA = {
    "ワイヤレスイヤホン": {
        "buy": [
            {"name": "Anker Soundcore Liberty 5 Bluetooth 5.4 完全ワイヤレス", "price": 14990, "platform": "Amazon", "image": "https://m.media-amazon.com/images/I/61GBMpGV6WL._AC_SL1500_.jpg"},
            {"name": "Anker Soundcore P40i Bluetooth 5.3 ノイズキャンセリング", "price": 7990, "platform": "Amazon", "image": "https://m.media-amazon.com/images/I/61w2MVhMJtL._AC_SL1500_.jpg"},
            {"name": "Anker Soundcore P31i Bluetooth 6.1 ワイヤレスイヤホン", "price": 5990, "platform": "Amazon", "image": "https://m.media-amazon.com/images/I/71Rb8hHD7vL._AC_SL1500_.jpg"},
            {"name": "AOKIMI ワイヤレスイヤホン Bluetooth V12 小型軽量", "price": 1966, "platform": "Amazon", "image": ""},
            {"name": "JBL TUNE BEAM ワイヤレスイヤホン ノイズキャンセリング", "price": 8800, "platform": "楽天", "image": ""},
            {"name": "SONY WF-1000XM5 ワイヤレスイヤホン ブラック", "price": 33000, "platform": "楽天", "image": ""},
        ],
        "sell": [
            {"name": "Anker Soundcore Liberty 5 ワイヤレスイヤホン", "price": 9980, "platform": "メルカリ(売却済)"},
            {"name": "Anker Soundcore Life P3 ワイヤレスイヤホン", "price": 2500, "platform": "メルカリ(売却済)"},
            {"name": "SONY WF-1000XM5 ワイヤレスイヤホン 中古美品", "price": 22000, "platform": "メルカリ(売却済)"},
            {"name": "Anker Soundcore P40i イヤホン 美品", "price": 5500, "platform": "メルカリ(売却済)"},
            {"name": "JBL TUNE BEAM ワイヤレスイヤホン 未開封", "price": 7200, "platform": "ヤフオク(落札)"},
            {"name": "Anker Soundcore Liberty 5 新品未使用", "price": 11500, "platform": "ヤフオク(落札)"},
        ],
    },
    "ポケモンカード": {
        "buy": [
            {"name": "ポケモンカード 拡張パック ムニキスゼロ 15パック", "price": 3980, "platform": "Amazon", "image": ""},
            {"name": "ポケモンカード 拡張パック ムニキスゼロ 10パック", "price": 2780, "platform": "Amazon", "image": ""},
            {"name": "ポケモンカード 強化拡張パック ポケモンカード151 BOX", "price": 27800, "platform": "Amazon", "image": ""},
            {"name": "ポケモンカード クレイバースト BOX シュリンク付き", "price": 8980, "platform": "楽天", "image": ""},
            {"name": "ポケモンカード バイオレットex BOX", "price": 5280, "platform": "楽天", "image": ""},
        ],
        "sell": [
            {"name": "ポケモンカード ムニキスゼロ 15パック まとめ", "price": 5720, "platform": "メルカリ(売却済)"},
            {"name": "ポケモンカード151 BOX 新品シュリンク付き", "price": 35000, "platform": "メルカリ(売却済)"},
            {"name": "ポケモンカード クレイバースト BOX シュリンク付", "price": 15800, "platform": "メルカリ(売却済)"},
            {"name": "ポケモンカード バイオレットex BOX", "price": 6800, "platform": "ヤフオク(落札)"},
            {"name": "ポケモンカード ムニキスゼロ 10パック", "price": 4200, "platform": "ヤフオク(落札)"},
        ],
    },
    "Nintendo Switch ソフト": {
        "buy": [
            {"name": "マリオカート8 デラックス Switch", "price": 5280, "platform": "Amazon", "image": ""},
            {"name": "ゼルダの伝説 ティアーズ オブ ザ キングダム Switch", "price": 6400, "platform": "Amazon", "image": ""},
            {"name": "スプラトゥーン3 Switch", "price": 4980, "platform": "楽天", "image": ""},
            {"name": "あつまれ どうぶつの森 Switch", "price": 4800, "platform": "楽天", "image": ""},
        ],
        "sell": [
            {"name": "マリオカート8 デラックス Switch ソフトのみ", "price": 4500, "platform": "メルカリ(売却済)"},
            {"name": "ゼルダの伝説 ティアーズ オブ ザ キングダム", "price": 5200, "platform": "メルカリ(売却済)"},
            {"name": "スプラトゥーン3 Switch 美品", "price": 3800, "platform": "ヤフオク(落札)"},
            {"name": "あつまれ どうぶつの森 Switch", "price": 3500, "platform": "ヤフオク(落札)"},
        ],
    },
    "デパコス 限定": {
        "buy": [
            {"name": "SUQQU シグニチャー カラー アイズ 限定 01", "price": 7700, "platform": "Amazon", "image": ""},
            {"name": "NARS オーガズム ブラッシュ ミニ 限定セット", "price": 4950, "platform": "Amazon", "image": ""},
            {"name": "MAC リップスティック 限定コレクション", "price": 3960, "platform": "楽天", "image": ""},
            {"name": "CHANEL ルージュ アリュール 限定色", "price": 5500, "platform": "楽天", "image": ""},
        ],
        "sell": [
            {"name": "SUQQU シグニチャー カラー アイズ 01 限定 新品", "price": 12000, "platform": "メルカリ(売却済)"},
            {"name": "NARS オーガズム ブラッシュ 限定 未使用", "price": 6500, "platform": "メルカリ(売却済)"},
            {"name": "MAC リップスティック 限定 完売品", "price": 5800, "platform": "メルカリ(売却済)"},
            {"name": "CHANEL ルージュ アリュール 限定色 新品", "price": 7800, "platform": "ヤフオク(落札)"},
        ],
    },
}

from matcher import is_same_product

def calc_profit(buy_price, sell_price, fee_rate, shipping, packing=50):
    fee = int(sell_price * fee_rate)
    total_cost = buy_price + fee + shipping + packing
    profit = sell_price - total_cost
    roi = (profit / buy_price * 100) if buy_price > 0 else 0
    return {"fee": fee, "total_cost": total_cost, "profit": profit, "roi": round(roi, 1)}

# ── UI ──
st.title("💰 せどり価格差リサーチツール")
st.caption("Amazon/楽天 仕入れ → メルカリ/ヤフオク 販売。利益商品を自動検出。")
st.info("デモ版: サンプルデータで動作を確認できます。製品版はリアルタイムスクレイピング対応。")

tab1, tab2, tab3 = st.tabs(["🔍 キーワード検索", "📁 ジャンル一括", "🧮 利益計算機"])

with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        keyword = st.selectbox("検索キーワード（デモ）", list(DEMO_DATA.keys()))
    with col2:
        min_profit = st.number_input("最低利益(円)", value=500, step=100)

    col_a, col_b = st.columns(2)
    with col_a:
        sell_platform = st.selectbox("販売先", list(FEES.keys()))
    with col_b:
        ship_type = st.selectbox("送料", list(SHIPPING.keys()))

    if st.button("🔍 リサーチ開始", type="primary", use_container_width=True):
        data = DEMO_DATA.get(keyword, {})
        buy_items = data.get("buy", [])
        sell_items = data.get("sell", [])

        fee_rate = FEES[sell_platform]
        ship_cost = SHIPPING[ship_type]

        results = []
        for b in buy_items:
            best_match = None; best_conf = 0; best_reason = ""
            for s in sell_items:
                is_match, conf, reason = is_same_product(b["name"], s["name"])
                if conf > best_conf:
                    best_conf = conf; best_match = s; best_reason = reason

            if best_match and best_conf > 0.5:
                sell_price = best_match["price"]
                match_info = f"{best_conf*100:.0f}% {best_reason}"
            else:
                s_prices = sorted([s["price"] for s in sell_items])
                sell_price = s_prices[len(s_prices)//2] if s_prices else 0
                match_info = "相場中央値"

            r = calc_profit(b["price"], sell_price, fee_rate, ship_cost)
            results.append({
                "商品名": b["name"][:50],
                "仕入先": b["platform"],
                "仕入値": b["price"],
                "販売予想": sell_price,
                "一致判定": match_info,
                "手数料": r["fee"],
                "送料": ship_cost,
                "純利益": r["profit"],
                "ROI": f"{r['roi']}%",
                "image": b.get("image", ""),
            })

        df = pd.DataFrame(results)
        profitable = df[df["純利益"] >= min_profit].sort_values("純利益", ascending=False)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("検索結果", f"{len(buy_items)}件")
        c2.metric("利益商品", f"{len(profitable)}件")
        c3.metric("最大利益", f"¥{int(profitable['純利益'].max()):,}" if len(profitable) > 0 else "¥0")
        avg_roi = profitable['ROI'].str.replace('%','').astype(float).mean() if len(profitable) > 0 else 0
        c4.metric("平均ROI", f"{avg_roi:.0f}%")

        if len(profitable) > 0:
            st.subheader(f"利益商品 ({len(profitable)}件)")
            for _, row in profitable.iterrows():
                with st.container():
                    cols = st.columns([1, 3, 1, 1, 1])
                    if row["image"]:
                        cols[0].image(row["image"], width=80)
                    else:
                        cols[0].write("📦")
                    cols[1].write(f"**{row['商品名']}**")
                    cols[1].caption(f"{row['仕入先']} | 一致: {row['一致判定']}")
                    cols[2].metric("仕入れ", f"¥{int(row['仕入値']):,}")
                    cols[3].metric("販売予想", f"¥{int(row['販売予想']):,}")
                    delta_color = "normal" if row["純利益"] > 0 else "inverse"
                    cols[4].metric("純利益", f"¥{int(row['純利益']):,}", delta=f"ROI {row['ROI']}", delta_color=delta_color)
                    st.divider()

            csv = profitable.drop(columns=["image"]).to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 CSVダウンロード", csv, "sedori_results.csv", "text/csv")
        else:
            st.info(f"利益{min_profit}円以上の商品は見つかりませんでした")

        # 全結果テーブル
        with st.expander("全結果を表示"):
            st.dataframe(df.drop(columns=["image"]), use_container_width=True)

with tab2:
    st.subheader("ジャンル一括リサーチ")
    st.caption("全カテゴリのデモデータを一括分析")
    if st.button("📁 全ジャンル一括リサーチ", type="primary"):
        all_results = []
        for kw, data in DEMO_DATA.items():
            for b in data["buy"]:
                s_prices = sorted([s["price"] for s in data["sell"]])
                s_med = s_prices[len(s_prices)//2] if s_prices else 0
                r = calc_profit(b["price"], s_med, 0.10, 210)
                if r["profit"] > 300:
                    all_results.append({
                        "キーワード": kw, "商品": b["name"][:40],
                        "仕入先": b["platform"], "仕入値": b["price"],
                        "販売予想": s_med, "純利益": r["profit"], "ROI": f"{r['roi']}%"
                    })
        if all_results:
            df = pd.DataFrame(all_results).sort_values("純利益", ascending=False)
            st.success(f"{len(all_results)}件の利益商品！")
            st.dataframe(df, use_container_width=True)

with tab3:
    st.subheader("利益計算機")
    c1, c2 = st.columns(2)
    with c1:
        bp = st.number_input("仕入れ値（円）", value=3000, step=100, key="bp")
        sp = st.number_input("販売予定価格（円）", value=5000, step=100, key="sp")
    with c2:
        pf = st.selectbox("販売先", list(FEES.keys()), key="pf2")
        sh = st.selectbox("送料", list(SHIPPING.keys()), key="sh2")
    if st.button("計算", use_container_width=True):
        r = calc_profit(bp, sp, FEES[pf], SHIPPING[sh])
        c1, c2, c3 = st.columns(3)
        c1.metric("総コスト", f"¥{r['total_cost']:,}")
        c2.metric("純利益", f"¥{r['profit']:,}", delta_color="normal" if r["profit"]>0 else "inverse")
        c3.metric("ROI", f"{r['roi']}%")

st.divider()
st.caption("せどり価格差リサーチツール v1.0 | デモ版")
