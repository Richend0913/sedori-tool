"""
商品一致判定モジュール
型番抽出 + 類似度で正確に同一商品かを判定
"""
import re
from difflib import SequenceMatcher

def extract_model_numbers(text: str) -> set:
    """商品名から型番を抽出"""
    # 英数字の組み合わせ（2文字以上）を型番候補として抽出
    # 例: P31i, Liberty5, V20i, A40, RTX4090, iPhone15
    patterns = [
        r'[A-Z][A-Za-z]+\s*\d+[A-Za-z]*',  # Liberty 5, Liberty5, P31i
        r'[A-Z]+[-]\d+[A-Za-z]*',           # RTX-4090, GT-R
        r'\d+[A-Z][A-Za-z]+',               # 15Pro, 4Pro
        r'[A-Z]{2,}\d+',                    # PS5, GT7, MG
        r'[A-Z][a-z]+\d+[a-z]*',            # Neo2, Air2
    ]
    models = set()
    for pat in patterns:
        for m in re.finditer(pat, text):
            candidate = m.group()
            if len(candidate) >= 2:
                models.add(candidate.upper())
    return models

def clean_name(text: str) -> str:
    """商品名をクリーニング（比較用）"""
    # 括弧内、装飾文字、スペースを除去
    text = re.sub(r'[【】\[\]()（）「」『』《》]', ' ', text)
    text = re.sub(r'[★☆♪♡◆●■▲▼]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()

def is_same_product(name_a: str, name_b: str) -> tuple[bool, float, str]:
    """
    2つの商品名が同一商品かを判定
    Returns: (is_match, confidence, reason)
    """
    clean_a = clean_name(name_a)
    clean_b = clean_name(name_b)

    # 1. 型番一致チェック（最も信頼性が高い）
    models_a = extract_model_numbers(name_a)
    models_b = extract_model_numbers(name_b)

    if models_a and models_b:
        common = models_a & models_b
        if common:
            # 型番が一致 → 高確率で同一商品
            return True, 0.95, f"型番一致: {common}"

        # 型番が両方あるが一致しない → 別商品の可能性が高い
        # ただし片方が部分的に含まれる場合はチェック
        partial = False
        for ma in models_a:
            for mb in models_b:
                if ma in mb or mb in ma:
                    partial = True
                    break
        if not partial:
            return False, 0.1, f"型番不一致: {models_a} vs {models_b}"

    # 2. 文字列類似度チェック
    sim = SequenceMatcher(None, clean_a, clean_b).ratio()

    # 3. キーワード一致チェック（語順に依存しない）
    words_a = set(re.findall(r'[a-z0-9\u3040-\u9fff]{2,}', clean_a))
    words_b = set(re.findall(r'[a-z0-9\u3040-\u9fff]{2,}', clean_b))
    if words_a and words_b:
        word_overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
    else:
        word_overlap = 0

    # 最終判定
    combined = sim * 0.4 + word_overlap * 0.6  # Word overlap weighted more (order-independent)

    if combined >= 0.65:
        return True, combined, f"高一致({combined:.0%})"
    elif combined >= 0.45:
        return False, combined, f"要確認({combined:.0%})"
    else:
        return False, combined, f"不一致({combined:.0%})"


if __name__ == "__main__":
    tests = [
        ("Anker Soundcore Liberty 5 Bluetooth 5.4 完全ワイヤレスイヤホン",
         "Anker soundcore Liberty 5 ワイヤレスイヤホン"),
        ("Anker Soundcore Liberty 5 Bluetooth",
         "Anker Soundcore P31i Bluetooth 6.1"),
        ("Anker Soundcore Liberty Neo 2",
         "Anker Soundcore Liberty 5"),
        ("Nintendo Switch マリオカート8 デラックス",
         "マリオカート8 デラックス Switch"),
        ("ポケモンカード ピカチュウ PSA10 マクドナルド",
         "ピカチュウ PSA10 マクドナルド プロモ"),
        ("iPhone 15 Pro Max 256GB",
         "iPhone 15 Pro Max 512GB"),
    ]

    for a, b in tests:
        match, conf, reason = is_same_product(a, b)
        status = "MATCH" if match else "NO"
        print(f"{status:5s} {conf:.0%} {reason}")
        print(f"  A: {a[:50]}")
        print(f"  B: {b[:50]}")
        print()
