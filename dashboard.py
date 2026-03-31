"""
chaco 統合ダッシュボード

Google系サービスのデータを1画面で確認できるダッシュボード。
credentials.json があれば実データ、なければモックデータで表示。

使い方:
    streamlit run dashboard.py

データソース (Phase 1):
    - GA4: chaco-memo / chaco38.com
    - AdMob: アプリ広告収益・eCPM・CTR
    - AdSense: Web広告収益
    - YouTube: chaco ch

将来対応 (Phase 2):
    - LINE公式アカウント配信統計
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# ---------------------------------------------------------------------------
# ページ設定
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="chaco 統合ダッシュボード",
    page_icon="favicon.png",
    layout="wide",
)

st.title("chaco 統合ダッシュボード")

# ---------------------------------------------------------------------------
# パスワード保護
# ---------------------------------------------------------------------------
def check_password():
    """Streamlit Secrets に設定したパスワードで認証する。"""
    if "password" not in st.secrets:
        return True  # パスワード未設定なら素通し

    if st.session_state.get("authenticated"):
        return True

    pwd = st.text_input("パスワードを入力してください", type="password")
    if pwd:
        if pwd == st.secrets["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("パスワードが正しくありません")
    return False

if not check_password():
    st.stop()

# ---------------------------------------------------------------------------
# 設定値
# ---------------------------------------------------------------------------
# GA4 プロパティID（Google Analytics の管理画面で確認可能）
GA4_PROPERTY_CHACOMEMO = "properties/526208629"   # chaco-memo アプリ
GA4_PROPERTY_CHACO38 = "properties/397084446"       # chaco38.com（小人の世界: Chacoのスタンプ）
YOUTUBE_CHANNEL_ID = "UC3r-zCwzrrzeKm1nEIvF0GA"   # Chaco38 (@chaco3881)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

# ---------------------------------------------------------------------------
# サイドバー: 期間選択
# ---------------------------------------------------------------------------
st.sidebar.header("設定")

today = datetime.now()
default_start = today - timedelta(days=7)

date_range = st.sidebar.date_input(
    "期間",
    value=(default_start, today),
)

# 期間が正しく選択されたか確認
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date = date_range[0].strftime("%Y-%m-%d")
    end_date = date_range[1].strftime("%Y-%m-%d")
else:
    start_date = default_start.strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# データ取得（API接続 or モック）
# ---------------------------------------------------------------------------
# credentials.json（ローカル）または Streamlit Secrets（クラウド）があればAPI接続
has_secrets = "google_token" in st.secrets if hasattr(st, "secrets") else False
use_api = os.path.exists(CREDENTIALS_FILE) or has_secrets

if use_api:
    st.sidebar.success("API接続: 有効")
    try:
        from google_auth import get_credentials
        from api_clients import (
            fetch_ga4_data, fetch_ga4_events,
            fetch_admob_data, fetch_adsense_data,
            fetch_youtube_data, fetch_youtube_channel_info,
        )
        creds = get_credentials()
    except Exception as e:
        st.sidebar.error(f"認証エラー: {e}")
        use_api = False
else:
    st.sidebar.warning("モックデータで表示中")
    st.sidebar.caption("credentials.json を配置するとAPI接続に切り替わります")

# --- GA4 (chaco-memo) ---
if use_api:
    try:
        df_app = fetch_ga4_data(creds, GA4_PROPERTY_CHACOMEMO, start_date, end_date)
        df_events = fetch_ga4_events(creds, GA4_PROPERTY_CHACOMEMO, start_date, end_date)
        app_data_source = "GA4 API"
    except Exception as e:
        st.sidebar.error(f"GA4エラー: {e}")
        use_api_ga4 = False
        df_app = None
else:
    df_app = None

# --- GA4 (chaco38.com) ---
if use_api and GA4_PROPERTY_CHACO38:
    try:
        df_web_ga4 = fetch_ga4_data(creds, GA4_PROPERTY_CHACO38, start_date, end_date)
        web_data_source = "GA4 API"
    except Exception as e:
        st.sidebar.error(f"GA4(chaco38)エラー: {e}")
        df_web_ga4 = None
else:
    df_web_ga4 = None

# --- AdMob ---
if use_api:
    try:
        df_admob = fetch_admob_data(creds, start_date, end_date)
        admob_data_source = "AdMob API"
    except Exception as e:
        st.sidebar.error(f"AdMobエラー: {e}")
        df_admob = None
else:
    df_admob = None

# --- AdSense ---
if use_api:
    try:
        df_adsense = fetch_adsense_data(creds, start_date, end_date)
        adsense_data_source = "AdSense API"
    except Exception as e:
        st.sidebar.error(f"AdSenseエラー: {e}")
        df_adsense = None
else:
    df_adsense = None

# --- YouTube ---
if use_api:
    try:
        df_youtube = fetch_youtube_data(creds, start_date, end_date, YOUTUBE_CHANNEL_ID)
        yt_channel = fetch_youtube_channel_info(creds, YOUTUBE_CHANNEL_ID)
        youtube_data_source = "YouTube API"
    except Exception as e:
        st.sidebar.error(f"YouTubeエラー: {e}")
        df_youtube = None
        yt_channel = {}
else:
    df_youtube = None
    yt_channel = {}

# --- モックデータにフォールバック ---
from api_clients import get_mock_data
df_mock = get_mock_data()

if df_app is None or len(df_app) == 0:
    df_app = df_mock[["日付", "DAU", "新規ユーザー", "エンゲージメント(秒)/人",
                       "セッション数", "PV"]].copy()
    app_data_source = "モック"

if df_admob is None or len(df_admob) == 0:
    df_admob = df_mock[["日付", "AdMob収益(円)", "eCPM(円)", "CTR(%)",
                         "表示回数"]].copy()
    admob_data_source = "モック"

if df_adsense is None or len(df_adsense) == 0:
    df_adsense = df_mock[["日付", "AdSense収益(円)", "AdSense PV"]].copy()
    adsense_data_source = "モック"

if df_youtube is None or len(df_youtube) == 0:
    df_youtube = df_mock[["日付", "YouTube視聴回数", "YouTube登録者増減"]].copy()
    youtube_data_source = "モック"

# ---------------------------------------------------------------------------
# セクション1: chaco-memo アプリ
# ---------------------------------------------------------------------------
st.header("📱 chaco-memo アプリ")
st.caption(f"データソース: {app_data_source}")

col1, col2, col3, col4 = st.columns(4)

latest_app = df_app.iloc[-1]
prev_app = df_app.iloc[-2] if len(df_app) >= 2 else latest_app

col1.metric(
    "DAU",
    f"{int(latest_app['DAU']):,}",
    f"{int(latest_app['DAU'] - prev_app['DAU']):+,}",
)
col2.metric(
    "新規ユーザー",
    f"{int(latest_app['新規ユーザー']):,}",
    f"{int(latest_app['新規ユーザー'] - prev_app['新規ユーザー']):+,}",
)

eng_sec = int(latest_app["エンゲージメント(秒)/人"])
col3.metric(
    "エンゲージメント/人",
    f"{eng_sec // 60}分{eng_sec % 60:02d}秒",
    f"{int(latest_app['エンゲージメント(秒)/人'] - prev_app['エンゲージメント(秒)/人']):+d}秒",
)
col4.metric(
    "累計ユーザー",
    f"{int(df_app['新規ユーザー'].sum()):,}",
)

# DAU + 新規ユーザーの2軸グラフ
fig_app = go.Figure()
fig_app.add_trace(go.Scatter(
    x=df_app["日付"], y=df_app["DAU"],
    name="DAU", mode="lines+markers", marker_color="#1976D2",
))
fig_app.add_trace(go.Bar(
    x=df_app["日付"], y=df_app["新規ユーザー"],
    name="新規ユーザー", marker_color="#81D4FA", yaxis="y2",
))
fig_app.update_layout(
    title="DAU & 新規ユーザー推移",
    yaxis=dict(title="DAU"),
    yaxis2=dict(title="新規ユーザー", overlaying="y", side="right"),
    height=320, margin=dict(t=40, b=20),
    legend=dict(orientation="h", y=-0.2),
)
st.plotly_chart(fig_app, use_container_width=True)

# イベントテーブル（API接続時のみ）
if use_api and "df_events" in dir() and df_events is not None and len(df_events) > 0:
    with st.expander("イベント別詳細"):
        st.dataframe(df_events, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# セクション2: AdMob 広告収益
# ---------------------------------------------------------------------------
st.header("💰 AdMob 広告収益")
st.caption(f"データソース: {admob_data_source}")

col1, col2, col3, col4 = st.columns(4)

latest_admob = df_admob.iloc[-1]
prev_admob = df_admob.iloc[-2] if len(df_admob) >= 2 else latest_admob

col1.metric(
    "日次収益",
    f"¥{int(latest_admob['AdMob収益(円)']):,}",
    f"¥{int(latest_admob['AdMob収益(円)'] - prev_admob['AdMob収益(円)']):+,}",
)
col2.metric(
    "累計収益",
    f"¥{int(df_admob['AdMob収益(円)'].sum()):,}",
)
col3.metric(
    "eCPM",
    f"¥{int(latest_admob['eCPM(円)']):,}",
    f"¥{int(latest_admob['eCPM(円)'] - prev_admob['eCPM(円)']):+,}",
)
col4.metric(
    "CTR",
    f"{latest_admob['CTR(%)']:.2f}%",
    f"{latest_admob['CTR(%)'] - prev_admob['CTR(%)']:.2f}%",
    delta_color="inverse",  # CTRは下がる方が良い
)

# 収益 + eCPM の2軸グラフ
fig_admob = go.Figure()
fig_admob.add_trace(go.Bar(
    x=df_admob["日付"], y=df_admob["AdMob収益(円)"],
    name="収益(円)", marker_color="#4CAF50",
))
fig_admob.add_trace(go.Scatter(
    x=df_admob["日付"], y=df_admob["eCPM(円)"],
    name="eCPM(円)", yaxis="y2",
    marker_color="#FF9800", mode="lines+markers",
))
fig_admob.update_layout(
    title="AdMob 日次収益 & eCPM",
    yaxis=dict(title="収益(円)"),
    yaxis2=dict(title="eCPM(円)", overlaying="y", side="right"),
    height=320, margin=dict(t=40, b=20),
    legend=dict(orientation="h", y=-0.2),
)
st.plotly_chart(fig_admob, use_container_width=True)

# CTR推移（目標ライン付き）
fig_ctr = px.line(
    df_admob, x="日付", y="CTR(%)",
    title="CTR 推移（目標: 1%以下）",
    markers=True,
)
fig_ctr.add_hline(
    y=1.0, line_dash="dash", line_color="red",
    annotation_text="目標ライン 1%",
)
fig_ctr.update_layout(height=250, margin=dict(t=40, b=20))
st.plotly_chart(fig_ctr, use_container_width=True)

# ---------------------------------------------------------------------------
# セクション3: AdSense + chaco38.com
# ---------------------------------------------------------------------------
st.header("🌐 Web (chaco38.com)")
st.caption(f"データソース: {adsense_data_source}")

col1, col2, col3 = st.columns(3)

latest_adsense = df_adsense.iloc[-1]
prev_adsense = df_adsense.iloc[-2] if len(df_adsense) >= 2 else latest_adsense

col1.metric(
    "AdSense 日次収益",
    f"¥{int(latest_adsense['AdSense収益(円)']):,}",
    f"¥{int(latest_adsense['AdSense収益(円)'] - prev_adsense['AdSense収益(円)']):+,}",
)
col2.metric(
    "AdSense 累計",
    f"¥{int(df_adsense['AdSense収益(円)'].sum()):,}",
)
col3.metric(
    "PV",
    f"{int(latest_adsense['AdSense PV']):,}",
    f"{int(latest_adsense['AdSense PV'] - prev_adsense['AdSense PV']):+,}",
)

fig_web = go.Figure()
fig_web.add_trace(go.Bar(
    x=df_adsense["日付"], y=df_adsense["AdSense収益(円)"],
    name="AdSense収益(円)", marker_color="#2196F3",
))
fig_web.add_trace(go.Scatter(
    x=df_adsense["日付"], y=df_adsense["AdSense PV"],
    name="PV", yaxis="y2",
    marker_color="#9C27B0", mode="lines+markers",
))
fig_web.update_layout(
    title="AdSense 収益 & PV",
    yaxis=dict(title="収益(円)"),
    yaxis2=dict(title="PV", overlaying="y", side="right"),
    height=320, margin=dict(t=40, b=20),
    legend=dict(orientation="h", y=-0.2),
)
st.plotly_chart(fig_web, use_container_width=True)

# ---------------------------------------------------------------------------
# セクション4: YouTube chaco ch
# ---------------------------------------------------------------------------
st.header("🎬 YouTube (chaco ch)")
st.caption(f"データソース: {youtube_data_source}")

# チャンネル基本情報（API接続時）
if yt_channel:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("チャンネル名", yt_channel.get("チャンネル名", "-"))
    col2.metric("登録者数", f"{yt_channel.get('登録者数', 0):,}")
    col3.metric("総視聴回数", f"{yt_channel.get('総視聴回数', 0):,}")
    col4.metric("動画数", f"{yt_channel.get('動画数', 0):,}")

# 動画別パフォーマンス（API接続時）
if use_api and df_youtube is not None and len(df_youtube) > 0 and "動画タイトル" in df_youtube.columns:
    total_views = int(df_youtube["YouTube視聴回数"].sum())
    total_likes = int(df_youtube["高評価数"].sum())
    col1, col2 = st.columns(2)
    col1.metric("動画合計視聴回数", f"{total_views:,}")
    col2.metric("動画合計高評価", f"{total_likes:,}")

    fig_yt = px.bar(
        df_youtube.head(10), x="YouTube視聴回数", y="動画タイトル",
        title="最近の動画 視聴回数",
        orientation="h",
    )
    fig_yt.update_layout(height=400, margin=dict(t=40, b=20), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_yt, use_container_width=True)

    with st.expander("動画別詳細"):
        st.dataframe(df_youtube, use_container_width=True, hide_index=True)
else:
    # モックデータの場合
    col1, col2, col3 = st.columns(3)
    latest_yt = df_youtube.iloc[-1]
    prev_yt = df_youtube.iloc[-2] if len(df_youtube) >= 2 else latest_yt
    col1.metric(
        "日次視聴回数",
        f"{int(latest_yt['YouTube視聴回数']):,}",
        f"{int(latest_yt['YouTube視聴回数'] - prev_yt['YouTube視聴回数']):+,}",
    )
    col2.metric("期間内合計視聴", f"{int(df_youtube['YouTube視聴回数'].sum()):,}")
    col3.metric("登録者増減", f"{int(latest_yt['YouTube登録者増減']):+,}")

    fig_yt = px.line(
        df_youtube, x="日付", y="YouTube視聴回数",
        title="YouTube 日次視聴回数", markers=True,
    )
    fig_yt.update_layout(height=320, margin=dict(t=40, b=20))
    st.plotly_chart(fig_yt, use_container_width=True)

# ---------------------------------------------------------------------------
# セクション5: 収益サマリー
# ---------------------------------------------------------------------------
st.header("📊 収益サマリー")

total_admob = int(df_admob["AdMob収益(円)"].sum())
total_adsense = int(df_adsense["AdSense収益(円)"].sum())
total_revenue = total_admob + total_adsense

col1, col2, col3 = st.columns(3)
col1.metric("AdMob 合計", f"¥{total_admob:,}")
col2.metric("AdSense 合計", f"¥{total_adsense:,}")
col3.metric("総収益", f"¥{total_revenue:,}")

# 収益構成比
fig_pie = px.pie(
    values=[total_admob, total_adsense],
    names=["AdMob（アプリ）", "AdSense（Web）"],
    title="収益構成比",
    color_discrete_sequence=["#4CAF50", "#2196F3"],
)
fig_pie.update_layout(height=300, margin=dict(t=40, b=20))
st.plotly_chart(fig_pie, use_container_width=True)

# ---------------------------------------------------------------------------
# フッター
# ---------------------------------------------------------------------------
st.divider()
if not use_api:
    st.caption(
        "⚠️ 現在はモックデータで表示しています。"
        "credentials.json を配置するとAPI接続に切り替わります。"
    )
st.caption("Phase 1: Google系（GA4 / AdMob / AdSense / YouTube）")
st.caption("Phase 2: LINE公式アカウント配信統計")
