#!/usr/bin/env python3
"""
deploy_times.py
===============
U&I株倶楽部新聞（朝刊・号外）をGitHub Pagesにデプロイし、
LINE U&I株倶楽部グループに自動通知するスクリプト。

使い方:
  # 朝刊
  python3 deploy_times.py morning <HTMLパス> <YYYY-MM-DD> "<見出し>"

  # 号外
  python3 deploy_times.py extra <HTMLパス> <YYYY-MM-DD> <スラッグ> "<見出し>"

オプション:
  --line    LINE通知を送信する（デフォルトはOFF）

例:
  python3 deploy_times.py morning ~/Desktop/UI_KabuClub_HP/morning_20260318.html 2026-03-18 "NVIDIA GTC効果で反発、本日FOMC"
  python3 deploy_times.py morning ~/Desktop/UI_KabuClub_HP/morning_20260318.html 2026-03-18 "見出し" --line
  python3 deploy_times.py extra ~/Desktop/UI_KabuClub_HP/gogai_gtc2026.html 2026-03-17 gtc-2026 "NVIDIA GTC 2026 完全レポート"
"""

import sys, os, shutil, subprocess, json, re
from datetime import datetime
try:
    import urllib.request as urlreq
    import urllib.error
except ImportError:
    pass

GITHUB_USERNAME = "yskzz121"
REPO_NAME       = "ui-kabu-times"
REPO_DIR        = os.path.expanduser("~/ui-kabu-times")
PAGES_BASE_URL  = f"https://{GITHUB_USERNAME}.github.io/{REPO_NAME}"
LINE_CONFIG     = os.path.expanduser("~/.line_config")

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


# ─────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────
def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, cwd=cwd or REPO_DIR,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"コマンド失敗: {cmd}\n{result.stderr}")
    return result.stdout.strip()


def load_line_config():
    config = {}
    if not os.path.exists(LINE_CONFIG):
        return config
    with open(LINE_CONFIG) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    return config


def send_line(token, group_id, message, max_retries=3):
    import time
    data = json.dumps({
        "to": group_id,
        "messages": [{"type": "text", "text": message}]
    }).encode("utf-8")
    for attempt in range(1, max_retries + 1):
        req = urlreq.Request(
            "https://api.line.me/v2/bot/message/push",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        try:
            with urlreq.urlopen(req, timeout=10) as res:
                return res.status == 200
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                wait = int(e.headers.get("Retry-After", 5 * attempt))
                print(f"  ⏳ レート制限（429）。{wait}秒後にリトライ ({attempt}/{max_retries})...")
                time.sleep(wait)
            else:
                print(f"⚠️  LINE送信エラー: {e}")
                return False
        except Exception as e:
            print(f"⚠️  LINE送信エラー: {e}")
            return False
    return False


def extract_headline(html_path):
    """HTMLから見出しを抽出（複数パターンにフォールバック）"""
    try:
        with open(html_path, encoding="utf-8") as f:
            content = f.read(30000)
        # 0. extra-headline メタタグ（号外用の短い見出し、最優先）
        m = re.search(r'name="extra-headline"\s+content="([^"]+)"', content)
        if m:
            return m.group(1).strip()[:80]
        # 1. summary-topic（朝刊マーケットサマリーの見出し）
        m = re.search(r'class="summary-topic[^"]*">(.*?)</span>', content)
        if m:
            return re.sub(r'<[^>]+>', '', m.group(1)).strip()
        # 2. top-story-title（朝刊TOP STORY）
        m = re.search(r'class="top-story-title">(.*?)</h2>', content, re.DOTALL)
        if m:
            return re.sub(r'<[^>]+>', '', m.group(1)).strip()[:80]
        # 3. og:description（OGPメタタグ）
        m = re.search(r'og:description"\s+content="([^"]+)"', content)
        if m:
            return m.group(1).strip()[:80]
        # 4. og:title から「—」以降を抽出（例: "号外 — NVIDIA GTC 2026 特集"）
        m = re.search(r'og:title"\s+content="[^"]*—\s*([^"]+)"', content)
        if m:
            return m.group(1).strip()[:80]
        # 5. <title>タグから「—」以降を抽出
        m = re.search(r'<title>[^<]*—\s*([^<]+)</title>', content)
        if m:
            return m.group(1).strip()[:80]
    except Exception:
        pass
    return ""


# ─────────────────────────────────────────
# latest.html updaters
# ─────────────────────────────────────────
def update_morning_latest(date_obj):
    y = date_obj.strftime("%Y")
    m = date_obj.strftime("%m")
    d = str(date_obj.day)
    rel = f"{y}/{m}/{d}.html"
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0;url={rel}">
<title>U&amp;I株倶楽部新聞 朝刊 - 最新号</title>
</head>
<body>
<p>最新号にリダイレクトしています... <a href="{rel}">こちらをクリック</a></p>
</body>
</html>
"""
    with open(os.path.join(REPO_DIR, "morning", "latest.html"), "w", encoding="utf-8") as f:
        f.write(html)


def update_extra_latest(date_obj, slug):
    y = date_obj.strftime("%Y")
    m = date_obj.strftime("%m")
    d = str(date_obj.day)
    rel = f"{y}/{m}/{d}-{slug}.html"
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0;url={rel}">
<title>U&amp;I株倶楽部新聞 号外 - 最新号</title>
</head>
<body>
<p>最新号にリダイレクトしています... <a href="{rel}">こちらをクリック</a></p>
</body>
</html>
"""
    with open(os.path.join(REPO_DIR, "extra", "latest.html"), "w", encoding="utf-8") as f:
        f.write(html)


# ─────────────────────────────────────────
# Portal index.html updater
# ─────────────────────────────────────────
def scan_articles(section_dir, article_type):
    """指定ディレクトリ内の全記事をスキャンして (date, rel_path, headline) のリストを返す"""
    articles = []
    base = os.path.join(REPO_DIR, section_dir)
    for root, dirs, files in os.walk(base):
        for fname in files:
            if not fname.endswith(".html") or fname in ("index.html", "latest.html"):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, REPO_DIR)
            # parse date from path
            parts = os.path.relpath(fpath, base).replace("\\", "/").split("/")
            if len(parts) == 3:  # YYYY/MM/{file}.html
                try:
                    y, m = int(parts[0]), int(parts[1])
                    if article_type == "morning":
                        d = int(parts[2].replace(".html", ""))
                    else:
                        d = int(parts[2].split("-")[0])
                    dt = datetime(y, m, d)
                    headline = extract_headline(fpath)
                    articles.append((dt, rel, headline))
                except (ValueError, IndexError):
                    pass
    articles.sort(key=lambda x: x[0], reverse=True)
    return articles


def rebuild_portal_index():
    """ポータルindex.htmlの朝刊・号外リストを更新"""
    index_path = os.path.join(REPO_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 号外リスト再構築（バナー形式）
    extras = scan_articles("extra", "extra")
    if extras:
        extra_items = ""
        for dt, rel, headline in extras:
            date_str = dt.strftime("%Y/%m/%d")
            title = headline if headline else os.path.basename(rel).replace(".html", "")
            extra_items += f'      <a class="extra-banner-item" href="{rel}">\n'
            extra_items += f'        <span class="extra-banner-badge">号外</span>\n'
            extra_items += f'        <span class="extra-banner-date">{date_str}</span>\n'
            extra_items += f'        <span class="extra-banner-title">{title}</span>\n'
            extra_items += f'      </a>\n'
        extra_block = f'    <div class="extra-banner-list" id="extraList">\n{extra_items}    </div>'
    else:
        extra_block = '    <div class="extra-banner-list" id="extraList">\n    </div>'

    # 朝刊リスト再構築
    mornings = scan_articles("morning", "morning")
    if mornings:
        morning_items = ""
        for dt, rel, headline in mornings:
            date_str = dt.strftime("%Y/%m/%d")
            title = headline if headline else f"{dt.month}月{dt.day}日の朝刊"
            morning_items += f'      <a class="article-item" href="{rel}">\n'
            morning_items += f'        <span class="article-date">{date_str}</span>\n'
            morning_items += f'        <span class="article-title">{title}</span>\n'
            morning_items += f'        <span class="article-tag morning">朝刊</span>\n'
            morning_items += f'      </a>\n'
        morning_block = f'    <div class="article-list" id="morningList">\n{morning_items}    </div>'
    else:
        morning_block = '    <div class="article-list" id="morningList">\n      <div class="empty-state">朝刊の記事はまだありません。近日公開予定です。</div>\n    </div>'

    # 号外バナーの内部リストを置換
    content = re.sub(
        r'(<!-- 号外 -->.*?)<div class="extra-banner-list" id="extraList">.*?</div>',
        lambda m: m.group(1) + extra_block,
        content, count=1, flags=re.DOTALL
    )

    # 朝刊セクションの article-list を置換
    content = re.sub(
        r'(<!-- 朝刊 -->.*?)<div class="article-list" id="morningList">.*?</div>',
        lambda m: m.group(1) + morning_block,
        content, count=1, flags=re.DOTALL
    )

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():
    if len(sys.argv) < 4:
        print("使い方:")
        print('  python3 deploy_times.py morning <HTMLパス> <YYYY-MM-DD> "<見出し>"')
        print('  python3 deploy_times.py extra <HTMLパス> <YYYY-MM-DD> <スラッグ> "<見出し>"')
        sys.exit(1)

    # --line フラグの検出（どの位置にあっても対応）
    send_line_flag = "--line" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--line"]

    article_type = args[0] if len(args) > 0 else ""
    html_path = os.path.abspath(args[1]) if len(args) > 1 else ""
    date_str = args[2] if len(args) > 2 else ""

    if article_type == "extra":
        slug = args[3] if len(args) > 3 else "special"
        headline = args[4] if len(args) > 4 else ""
    else:
        slug = None
        headline = args[3] if len(args) > 3 else ""

    if not os.path.exists(html_path):
        print(f"❌ ファイルが見つかりません: {html_path}")
        sys.exit(1)

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    y = date_obj.strftime("%Y")
    m = date_obj.strftime("%m")
    d = str(date_obj.day)
    weekday = WEEKDAYS[date_obj.weekday()]

    type_label = "朝刊" if article_type == "morning" else "号外"
    type_icon = "📰" if article_type == "morning" else "🔴"

    print(f"{type_icon} U&I株倶楽部新聞 {type_label}デプロイ")
    print(f"   日付: {y}年{int(m)}月{d}日（{weekday}）")
    if slug:
        print(f"   スラッグ: {slug}")
    print()

    # 0. ブランチチェック（gh-pages以外なら中断）
    current_branch = run("git rev-parse --abbrev-ref HEAD", cwd=REPO_DIR)
    if current_branch != "gh-pages":
        print(f"❌ エラー: 現在のブランチが '{current_branch}' です。'gh-pages' に切り替えてください。")
        print(f"   → cd {REPO_DIR} && git checkout gh-pages")
        sys.exit(1)

    # 1. git pull
    print("1️⃣  リポジトリを最新化...")
    run("git pull --rebase", cwd=REPO_DIR)

    # 2. HTMLをコピー
    if article_type == "morning":
        dest_dir = os.path.join(REPO_DIR, "morning", y, m)
        fname = f"{d}.html"
    else:
        dest_dir = os.path.join(REPO_DIR, "extra", y, m)
        fname = f"{d}-{slug}.html"

    os.makedirs(dest_dir, exist_ok=True)
    dest_file = os.path.join(dest_dir, fname)
    shutil.copy2(html_path, dest_file)
    print(f"2️⃣  HTMLをコピー → {article_type}/{y}/{m}/{fname}")

    # 3. latest.html 更新
    if article_type == "morning":
        update_morning_latest(date_obj)
    else:
        update_extra_latest(date_obj, slug)
    print(f"3️⃣  {article_type}/latest.html を更新")

    # 4. ポータルindex.html 再構築
    rebuild_portal_index()
    print("4️⃣  ポータル index.html を再構築")

    # 5. git add → commit → push
    print("5️⃣  Git コミット & プッシュ...")
    run("git add -A", cwd=REPO_DIR)
    commit_msg = f"{type_icon} {type_label} {y}/{int(m)}/{d}（{weekday}）"
    if slug:
        commit_msg += f" {slug}"
    run(f'git commit -m "{commit_msg}"', cwd=REPO_DIR)
    run("git push", cwd=REPO_DIR)
    print("   ✅ GitHub Pages にプッシュ完了")

    # 6. LINE通知
    if not send_line_flag:
        print("6️⃣  LINE通知... スキップ（--line フラグなし）")
    else:
        print("6️⃣  LINE通知...")
    line_cfg = load_line_config() if send_line_flag else {}
    token = line_cfg.get("LINE_TOKEN")
    group_id = line_cfg.get("LINE_GROUP_ID")

    if send_line_flag and token and group_id:
        url = f"{PAGES_BASE_URL}/{article_type}/{y}/{m}/{fname}"
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        msg = f"{type_icon} 【U&I株倶楽部 {type_label}】{y}年{int(m)}月{d}日（{weekday}）\n"
        if headline:
            msg += f"💬 {headline}\n"
        msg += (
            f"\n"
            f"🔗 {type_label}はこちら:\n"
            f"{url}\n"
            f"\n"
            f"🏠 新聞ポータル:\n"
            f"{PAGES_BASE_URL}/\n"
            f"\n"
            f"({now_str} 自動配信)"
        )
        ok = send_line(token, group_id, msg)
        if ok:
            print("   ✅ LINE通知 送信完了")
        else:
            print("   ⚠️  LINE通知 送信失敗（記事は公開済み）")
    elif send_line_flag:
        print("   ⚠️  LINE設定が見つかりません（スキップ）")

    print()
    url = f"{PAGES_BASE_URL}/{article_type}/{y}/{m}/{fname}"
    print(f"🎉 デプロイ完了!")
    print(f"   📎 {url}")


if __name__ == "__main__":
    main()
