#!/usr/bin/env python3
"""
LINE スタンプ月次販売分析スクリプト
===================================
デザイン＆ランゲージ株式会社 マーケティング部

使い方:
  python3 line_stamp_monthly_report.py <CSVファイルパス>

例:
  python3 line_stamp_monthly_report.py ~/Downloads/report-xxxxx-2026-03-14.csv

出力:
  - ターミナルに分析結果を表示
  - 同じディレクトリに「月次レポート_YYYY年MM月.txt」を保存

CSVの構造（LINE Creators Market のレポート形式）:
  - Revenue Share Rate = 35.0 → 通常販売
  - Revenue Share Rate = 20.0 → 販売（低レート）
  - Revenue Share Rate = 空欄 → プレミアム（使い放題サービス分配金）
  - Type: Sticker（スタンプ）, Emoji（絵文字）, Theme（着せ替え）
"""

import csv
import sys
import os
from collections import defaultdict
from datetime import datetime


# ===========================================================
# ユーティリティ関数
# ===========================================================

def to_int(s):
    """文字列を整数に変換。変換できない場合は0を返す"""
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def load_csv(filepath):
    """CSVファイルを読み込み、有効な行（Typeあり）のリストを返す"""
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Type'):  # Type列が空の行はスキップ
                rows.append(row)
    return rows


def classify_row(row):
    """
    行を販売チャネルに分類する
    Returns: 'sales'（通常販売）, 'premium'（プレミアム）
    """
    rate = row.get('Revenue Share Rate', '')
    if rate in ('35.0', '20.0'):
        return 'sales'
    else:
        return 'premium'


def type_label(type_en):
    """英語のType名を日本語に変換"""
    labels = {
        'Sticker': 'スタンプ',
        'Emoji': '絵文字',
        'Theme': '着せ替え'
    }
    return labels.get(type_en, type_en)


def type_short(type_en):
    """英語のType名を1文字略称に変換"""
    shorts = {
        'Sticker': 'ス',
        'Emoji': '絵',
        'Theme': '着'
    }
    return shorts.get(type_en, '?')


# ===========================================================
# 分析関数
# ===========================================================

def overall_summary(rows):
    """全体サマリーを計算"""
    sales_rows = [r for r in rows if classify_row(r) == 'sales']
    premium_rows = [r for r in rows if classify_row(r) == 'premium']

    result = {
        'sales': {
            'amount': sum(to_int(r['Sales']) for r in sales_rows),
            'counts': sum(to_int(r['Sales Counts']) for r in sales_rows),
            'revenue_pretax': sum(to_int(r['Revenue Share (Pre-Tax)']) for r in sales_rows),
            'revenue': sum(to_int(r['Revenue Share']) for r in sales_rows),
        },
        'premium': {
            'revenue': sum(to_int(r['Revenue Share']) for r in premium_rows),
        }
    }
    result['total_revenue'] = result['sales']['revenue'] + result['premium']['revenue']
    return result


def type_breakdown(rows):
    """タイプ別（スタンプ/絵文字/着せ替え）× 販売/プレミアム 集計"""
    results = {}
    for type_name in ['Sticker', 'Emoji', 'Theme']:
        type_rows = [r for r in rows if r['Type'] == type_name]
        sales = [r for r in type_rows if classify_row(r) == 'sales']
        premium = [r for r in type_rows if classify_row(r) == 'premium']

        s_rev = sum(to_int(r['Revenue Share']) for r in sales)
        p_rev = sum(to_int(r['Revenue Share']) for r in premium)
        total = s_rev + p_rev

        results[type_name] = {
            'sales_revenue': s_rev,
            'sales_amount': sum(to_int(r['Sales']) for r in sales),
            'sales_counts': sum(to_int(r['Sales Counts']) for r in sales),
            'premium_revenue': p_rev,
            'total_revenue': total,
            'premium_ratio': (p_rev / total * 100) if total > 0 else 0,
            'product_count': len(set(r['Item ID'] for r in type_rows)),
            'selling_count': len(set(r['Item ID'] for r in sales)),
        }
    return results


def country_breakdown(rows):
    """国別売上集計"""
    country_data = defaultdict(lambda: {'sales': 0, 'revenue': 0, 'counts': 0})
    for r in rows:
        if classify_row(r) == 'sales':
            country = r.get('Country of Sale', 'Unknown')
            country_data[country]['sales'] += to_int(r['Sales'])
            country_data[country]['revenue'] += to_int(r['Revenue Share'])
            country_data[country]['counts'] += to_int(r['Sales Counts'])

    # 売上順にソート
    sorted_countries = sorted(country_data.items(), key=lambda x: -x[1]['sales'])
    return sorted_countries


def top_items(rows, channel='sales', limit=15):
    """
    商品別ランキング
    channel: 'sales'（通常販売）or 'premium'（プレミアム）
    """
    item_agg = defaultdict(lambda: {
        'title': '', 'type': '', 'sales': 0, 'counts': 0, 'revenue': 0
    })

    target_rows = [r for r in rows if classify_row(r) == channel]

    for r in target_rows:
        iid = r['Item ID']
        item_agg[iid]['title'] = r['Item Title']
        item_agg[iid]['type'] = r['Type']
        item_agg[iid]['sales'] += to_int(r['Sales'])
        item_agg[iid]['counts'] += to_int(r['Sales Counts'])
        item_agg[iid]['revenue'] += to_int(r['Revenue Share'])

    # 分配金順にソート
    sorted_items = sorted(item_agg.items(), key=lambda x: -x[1]['revenue'])
    return sorted_items[:limit]


def overseas_analysis(rows):
    """海外売上の分析"""
    countries = country_breakdown(rows)
    jp_sales = sum(d['sales'] for c, d in countries if c == 'JP')
    overseas_sales = sum(d['sales'] for c, d in countries if c != 'JP')
    total = jp_sales + overseas_sales
    overseas_ratio = (overseas_sales / total * 100) if total > 0 else 0

    # 海外のみ抽出
    overseas_countries = [(c, d) for c, d in countries if c != 'JP']

    return {
        'jp_sales': jp_sales,
        'overseas_sales': overseas_sales,
        'overseas_ratio': overseas_ratio,
        'countries': overseas_countries
    }


# ===========================================================
# レポート出力
# ===========================================================

def generate_report(rows, period_label):
    """分析結果をフォーマットされたレポート文字列として返す"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"LINE スタンプ月次販売レポート: {period_label}")
    lines.append(f"デザイン＆ランゲージ株式会社 マーケティング部")
    lines.append(f"作成日: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("=" * 60)

    # --- 全体サマリー ---
    summary = overall_summary(rows)
    lines.append("\n【1】全体サマリー")
    lines.append("-" * 40)
    lines.append(f"  通常販売:")
    lines.append(f"    売上額:       ¥{summary['sales']['amount']:,}")
    lines.append(f"    販売個数:     {summary['sales']['counts']:,}個")
    lines.append(f"    分配金(税前): ¥{summary['sales']['revenue_pretax']:,}")
    lines.append(f"    分配金(税込): ¥{summary['sales']['revenue']:,}")
    lines.append(f"  プレミアム（使い放題）:")
    lines.append(f"    分配金(税込): ¥{summary['premium']['revenue']:,}")
    lines.append(f"  合計分配金(税込): ¥{summary['total_revenue']:,}")

    s_pct = summary['sales']['revenue'] / summary['total_revenue'] * 100 if summary['total_revenue'] else 0
    p_pct = summary['premium']['revenue'] / summary['total_revenue'] * 100 if summary['total_revenue'] else 0
    lines.append(f"  構成比: 販売 {s_pct:.1f}% / プレミアム {p_pct:.1f}%")

    # --- タイプ別 ---
    types = type_breakdown(rows)
    lines.append(f"\n【2】タイプ別 内訳")
    lines.append("-" * 40)
    for t in ['Sticker', 'Emoji', 'Theme']:
        d = types[t]
        lines.append(f"  ■ {type_label(t)}")
        lines.append(f"    商品数: {d['product_count']}（うち販売実績あり: {d['selling_count']}）")
        lines.append(f"    通常販売:   ¥{d['sales_revenue']:,}  ({100 - d['premium_ratio']:.1f}%)")
        lines.append(f"    プレミアム: ¥{d['premium_revenue']:,}  ({d['premium_ratio']:.1f}%)")
        lines.append(f"    合計:       ¥{d['total_revenue']:,}")

    # --- 海外分析 ---
    overseas = overseas_analysis(rows)
    lines.append(f"\n【3】海外売上分析")
    lines.append("-" * 40)
    lines.append(f"  国内(JP): ¥{overseas['jp_sales']:,}")
    lines.append(f"  海外合計: ¥{overseas['overseas_sales']:,}")
    lines.append(f"  海外比率: {overseas['overseas_ratio']:.1f}%")
    if overseas['countries']:
        lines.append(f"  海外内訳:")
        for country, d in overseas['countries'][:10]:
            lines.append(f"    {country}: ¥{d['sales']:,} ({d['counts']}個)")

    # --- トップセラー（通常販売）---
    lines.append(f"\n【4】通常販売 分配金ランキング TOP15")
    lines.append("-" * 40)
    for i, (iid, d) in enumerate(top_items(rows, 'sales', 15), 1):
        lines.append(f"  {i:2}. [{type_short(d['type'])}] {d['title']}")
        lines.append(f"      売上¥{d['sales']:,} / {d['counts']}個 / 分配金¥{d['revenue']:,}")

    # --- トップセラー（プレミアム）---
    lines.append(f"\n【5】プレミアム 分配金ランキング TOP15")
    lines.append("-" * 40)
    for i, (iid, d) in enumerate(top_items(rows, 'premium', 15), 1):
        lines.append(f"  {i:2}. [{type_short(d['type'])}] {d['title']}")
        lines.append(f"      プレミアム分配金¥{d['revenue']:,}")

    # --- キャラクター分析（簡易）---
    lines.append(f"\n【6】キャラクター別 売上傾向（通常販売+プレミアム）")
    lines.append("-" * 40)

    # キーワードベースで主要キャラを集計
    # ※ カスタマイズポイント: ここにキャラ名を追加できます
    character_keywords = {
        'パンダ / Panda': ['panda', 'パンダ'],
        '柴犬 / Shiba': ['shiba', 'しば', '柴'],
        'ひつじ / Sheep': ['sheep', 'ひつじ', '羊'],
        'くますけ / Kumasuke': ['kumasuke', 'くますけ'],
        '猫 / Cat': ['cat', '猫', 'ねこ', 'neko', 'nyago'],
        'ハムスター / Hamster': ['hamster', 'ハムスター'],
        'うさこ / Usako': ['usako', 'うさこ'],
    }

    char_totals = {}
    for char_name, keywords in character_keywords.items():
        total_rev = 0
        for r in rows:
            title = (r.get('Item Title', '') or '').lower()
            if any(kw.lower() in title for kw in keywords):
                total_rev += to_int(r['Revenue Share'])
        if total_rev > 0:
            char_totals[char_name] = total_rev

    for char, rev in sorted(char_totals.items(), key=lambda x: -x[1]):
        pct = rev / summary['total_revenue'] * 100 if summary['total_revenue'] else 0
        lines.append(f"  {char}: ¥{rev:,} ({pct:.1f}%)")

    lines.append("\n" + "=" * 60)
    lines.append("レポート終了")
    lines.append("=" * 60)

    return "\n".join(lines)


# ===========================================================
# メイン処理
# ===========================================================

def main():
    # コマンドライン引数からCSVパスを取得
    if len(sys.argv) < 2:
        print("使い方: python3 line_stamp_monthly_report.py <CSVファイルパス>")
        print("例:     python3 line_stamp_monthly_report.py ~/Downloads/report-xxx.csv")
        sys.exit(1)

    csv_path = sys.argv[1]

    if not os.path.exists(csv_path):
        print(f"エラー: ファイルが見つかりません: {csv_path}")
        sys.exit(1)

    # CSV読み込み
    print(f"読み込み中: {csv_path}")
    rows = load_csv(csv_path)
    print(f"  有効行数: {len(rows)}")

    # 期間をデータから取得
    if rows:
        period_from = rows[0].get('From (GMT+9:00)', '')
        period_to = rows[0].get('To (GMT+9:00)', '')
        # "2026.02.01" → "2026年2月"
        try:
            dt = datetime.strptime(period_from, '%Y.%m.%d')
            period_label = f"{dt.year}年{dt.month}月"
        except ValueError:
            period_label = f"{period_from} - {period_to}"
    else:
        period_label = "不明"

    # レポート生成
    report = generate_report(rows, period_label)

    # ターミナルに表示
    print("\n" + report)

    # ファイルに保存
    output_dir = os.path.dirname(csv_path)
    output_filename = f"月次レポート_{period_label}.txt"
    output_path = os.path.join(output_dir, output_filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n保存しました: {output_path}")


if __name__ == '__main__':
    main()
