"""
各Google APIのデータ取得クライアント

各関数は pandas DataFrame を返す。
API接続できない場合はモックデータにフォールバックする。

データソース:
    - GA4 Data API: アプリ / Webサイト
    - AdMob API: アプリ広告収益
    - AdSense Management API: Web広告収益
    - YouTube Data API v3: チャンネル統計
"""

import pandas as pd
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# GA4 (Google Analytics Data API)
# ---------------------------------------------------------------------------
def fetch_ga4_data(creds, property_id, start_date, end_date):
    """
    GA4からDAU・新規ユーザー・エンゲージメント時間を日次で取得する。

    Args:
        creds: Google OAuth2 認証情報
        property_id: GA4 プロパティID（例: "properties/123456789"）
        start_date: 開始日（"YYYY-MM-DD"）
        end_date: 終了日（"YYYY-MM-DD"）

    Returns:
        DataFrame: 日付, activeUsers, newUsers, userEngagementDuration 等
    """
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        RunReportRequest, DateRange, Dimension, Metric,
    )

    client = BetaAnalyticsDataClient(credentials=creds)

    request = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="date")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="userEngagementDuration"),
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="engagedSessions"),
        ],
    )

    response = client.run_report(request)

    rows = []
    for row in response.rows:
        date_str = row.dimension_values[0].value  # "20260323" 形式
        rows.append({
            "日付": pd.to_datetime(date_str, format="%Y%m%d"),
            "DAU": int(row.metric_values[0].value),
            "新規ユーザー": int(row.metric_values[1].value),
            "エンゲージメント(秒)": float(row.metric_values[2].value),
            "セッション数": int(row.metric_values[3].value),
            "PV": int(row.metric_values[4].value),
            "エンゲージセッション": int(row.metric_values[5].value),
        })

    df = pd.DataFrame(rows).sort_values("日付").reset_index(drop=True)

    # 1ユーザーあたりのエンゲージメント秒数に変換
    if len(df) > 0:
        df["エンゲージメント(秒)/人"] = (
            df["エンゲージメント(秒)"] / df["DAU"].replace(0, 1)
        ).round(0).astype(int)

    return df


def fetch_ga4_events(creds, property_id, start_date, end_date):
    """
    GA4 からイベント別のカウントを取得する（first_open, app_remove 等）。
    """
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        RunReportRequest, DateRange, Dimension, Metric,
    )

    client = BetaAnalyticsDataClient(credentials=creds)

    request = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="eventName")],
        metrics=[
            Metric(name="eventCount"),
            Metric(name="totalUsers"),
        ],
    )

    response = client.run_report(request)

    rows = []
    for row in response.rows:
        rows.append({
            "イベント名": row.dimension_values[0].value,
            "イベント数": int(row.metric_values[0].value),
            "ユーザー数": int(row.metric_values[1].value),
        })

    return pd.DataFrame(rows).sort_values("イベント数", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# AdSense Management API
# ---------------------------------------------------------------------------
def fetch_adsense_data(creds, start_date, end_date):
    """
    AdSenseから日次の収益データを取得する。

    Returns:
        DataFrame: 日付, 収益(円), PV, クリック数, CPC
    """
    from googleapiclient.discovery import build

    service = build("adsense", "v2", credentials=creds)

    # アカウントID を取得
    accounts = service.accounts().list().execute()
    if not accounts.get("accounts"):
        return pd.DataFrame()
    account_id = accounts["accounts"][0]["name"]

    # レポート取得
    result = service.accounts().reports().generate(
        account=account_id,
        dateRange="CUSTOM",
        startDate_year=int(start_date[:4]),
        startDate_month=int(start_date[5:7]),
        startDate_day=int(start_date[8:10]),
        endDate_year=int(end_date[:4]),
        endDate_month=int(end_date[5:7]),
        endDate_day=int(end_date[8:10]),
        dimensions=["DATE"],
        metrics=["ESTIMATED_EARNINGS", "PAGE_VIEWS", "CLICKS", "COST_PER_CLICK"],
        currencyCode="JPY",
    ).execute()

    rows = []
    for row in result.get("rows", []):
        cells = row["cells"]
        rows.append({
            "日付": pd.to_datetime(cells[0]["value"]),
            "AdSense収益(円)": float(cells[1]["value"]),
            "AdSense PV": int(cells[2]["value"]),
            "AdSenseクリック数": int(cells[3]["value"]),
            "CPC(円)": float(cells[4]["value"]),
        })

    return pd.DataFrame(rows).sort_values("日付").reset_index(drop=True)


# ---------------------------------------------------------------------------
# AdMob API
# ---------------------------------------------------------------------------
def fetch_admob_data(creds, start_date, end_date):
    """
    AdMobから日次の広告収益データを取得する。

    Returns:
        DataFrame: 日付, 収益(円), eCPM, 表示回数, クリック率
    """
    from googleapiclient.discovery import build
    import google_auth_httplib2
    import httplib2

    http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http())
    service = build("admob", "v1", http=http)

    # アカウントID を取得
    accounts = service.accounts().list().execute()
    if not accounts.get("account"):
        return pd.DataFrame()
    account_id = accounts["account"][0]["name"]

    # ネットワークレポート取得
    # 日付をAPIが求める形式に変換
    sd = datetime.strptime(start_date, "%Y-%m-%d")
    ed = datetime.strptime(end_date, "%Y-%m-%d")

    request_body = {
        "reportSpec": {
            "dateRange": {
                "startDate": {"year": sd.year, "month": sd.month, "day": sd.day},
                "endDate": {"year": ed.year, "month": ed.month, "day": ed.day},
            },
            "dimensions": ["DATE", "APP"],
            "metrics": [
                "ESTIMATED_EARNINGS",
                "AD_REQUESTS",
                "IMPRESSIONS",
                "CLICKS",
            ],
        }
    }

    result = service.accounts().networkReport().generate(
        parent=account_id, body=request_body
    ).execute()

    rows = []
    for item in result:
        row_data = item.get("row", {})
        if not row_data:
            continue
        dim = row_data.get("dimensionValues", {})
        met = row_data.get("metricValues", {})

        date_val = dim.get("DATE", {}).get("value", "")
        if not date_val:
            continue

        impressions = int(met.get("IMPRESSIONS", {}).get("integerValue", 0))
        clicks = int(met.get("CLICKS", {}).get("integerValue", 0))
        earnings_micros = int(met.get("ESTIMATED_EARNINGS", {}).get("microsValue", 0))
        earnings_yen = earnings_micros / 1_000_000

        ecpm = (earnings_yen / impressions * 1000) if impressions > 0 else 0
        ctr = (clicks / impressions * 100) if impressions > 0 else 0

        rows.append({
            "日付": pd.to_datetime(date_val, format="%Y%m%d"),
            "アプリ": dim.get("APP", {}).get("value", ""),
            "AdMob収益(円)": round(earnings_yen),
            "eCPM(円)": round(ecpm),
            "表示回数": impressions,
            "クリック数": clicks,
            "CTR(%)": round(ctr, 2),
        })

    return pd.DataFrame(rows).sort_values("日付").reset_index(drop=True)


# ---------------------------------------------------------------------------
# YouTube Analytics API
# ---------------------------------------------------------------------------
def fetch_youtube_data(creds, start_date, end_date, channel_id=None):
    """
    YouTube Data API v3 で最近の動画のパフォーマンスを取得する。
    （YouTube Analytics API はブランドアカウントに直接アクセスできないため）

    Returns:
        DataFrame: 動画タイトル, 公開日, 視聴回数, 高評価数, コメント数
    """
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", credentials=creds)

    # チャンネルの最近の動画を検索
    search_result = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        order="date",
        maxResults=20,
        type="video",
        publishedAfter=f"{start_date}T00:00:00Z",
        publishedBefore=f"{end_date}T23:59:59Z",
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search_result.get("items", [])]

    if not video_ids:
        # 期間内に動画がなければ最新20件を取得
        search_result = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            order="date",
            maxResults=20,
            type="video",
        ).execute()
        video_ids = [item["id"]["videoId"] for item in search_result.get("items", [])]

    if not video_ids:
        return pd.DataFrame()

    # 各動画の統計情報を取得
    stats_result = youtube.videos().list(
        part="statistics,snippet",
        id=",".join(video_ids),
    ).execute()

    rows = []
    for video in stats_result.get("items", []):
        stats = video["statistics"]
        snippet = video["snippet"]
        rows.append({
            "動画タイトル": snippet["title"],
            "公開日": pd.to_datetime(snippet["publishedAt"]).strftime("%Y-%m-%d"),
            "YouTube視聴回数": int(stats.get("viewCount", 0)),
            "高評価数": int(stats.get("likeCount", 0)),
            "コメント数": int(stats.get("commentCount", 0)),
        })

    return pd.DataFrame(rows)


def fetch_youtube_channel_info(creds, channel_id=None):
    """
    チャンネルの基本情報（登録者数、総視聴回数、動画数）を取得する。
    """
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", credentials=creds)

    if channel_id:
        result = youtube.channels().list(
            part="statistics,snippet",
            id=channel_id,
        ).execute()
    else:
        result = youtube.channels().list(
            part="statistics,snippet",
            mine=True,
        ).execute()

    if not result.get("items"):
        return {}

    ch = result["items"][0]
    stats = ch["statistics"]
    return {
        "チャンネル名": ch["snippet"]["title"],
        "登録者数": int(stats.get("subscriberCount", 0)),
        "総視聴回数": int(stats.get("viewCount", 0)),
        "動画数": int(stats.get("videoCount", 0)),
    }


# ---------------------------------------------------------------------------
# モックデータ（API未接続時のフォールバック）
# ---------------------------------------------------------------------------
def get_mock_data():
    """実績値をベースにしたモックデータを返す。"""
    dates = pd.date_range("2026-03-23", "2026-03-31")
    return pd.DataFrame({
        "日付": dates,
        "DAU": [660, 350, 220, 183, 160, 144, 145, 143, 180],
        "新規ユーザー": [689, 248, 55, 32, 26, 8, 8, 24, 40],
        "エンゲージメント(秒)/人": [131, 171, 200, 242, 270, 287, 305, 322, 353],
        "セッション数": [660, 400, 280, 250, 230, 210, 220, 215, 260],
        "PV": [5500, 3200, 2100, 1800, 1600, 1400, 1450, 1400, 1700],
        "AdMob収益(円)": [183, 200, 210, 230, 195, 180, 175, 190, 220],
        "eCPM(円)": [76, 120, 150, 165, 175, 185, 195, 197, 210],
        "CTR(%)": [5.50, 4.20, 3.50, 3.29, 2.89, 2.45, 2.10, 1.89, 1.71],
        "表示回数": [2400, 1600, 1400, 1200, 1100, 950, 900, 950, 1050],
        "AdSense収益(円)": [45, 52, 38, 61, 55, 48, 42, 50, 58],
        "AdSense PV": [320, 280, 310, 350, 290, 270, 260, 300, 340],
        "YouTube視聴回数": [150, 180, 160, 200, 170, 190, 210, 220, 250],
        "YouTube登録者増減": [2, 3, 1, 4, 2, 3, 5, 3, 4],
    })
