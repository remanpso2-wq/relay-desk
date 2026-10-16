# 検証結果 — 2026-10-16

このプロジェクト独自の実行結果です。NAVILOGや他作品の結果は流用していません。

| 項目 | 結果 | 証拠/範囲 |
|---|---|---|
| pytest | 37成功 | results/pytest.txt。SQLite API、認可、企業分離、CSRF、失効、版の競合、AI失敗、引用ID、予約・回数制限、初期移行、同時承認、内部メモ、停止復旧、チャンク検索回帰、SQLite復元 |
| React/TypeScript | 成功 | results/build.txt。TypeScript strict + Viteビルド |
| 初期セットアップ | 成功 | results/setup-smoke.txt。空DBへAlembic、架空データ、ログイン、5問い合わせ・4資料、ビルド済みHTML配信をASGI TestClientで検証 |
| npm audit | 検査時点で既知脆弱性0件 | results/npm-audit.json |
| pip-audit | 固定した実行依存で検査時点0件 | results/python-audit.json。lockの列挙依存、--no-deps --disable-pip |
| OpenAPI | 現在のアプリから生成 | openapi.json |
| PostgreSQL実DB | 未実行 | パッケージ導入を試行したが、環境のsetgroups/setuid権限制約で失敗。CI定義あり。SQLite成功で代替しない |
| Docker Compose | 未実行 | Dockerfile・Compose定義のみ |
| Windows | 未実行 | PowerShell向け手順あり |
| E2E | 未実行 | Playwright 2シナリオのテスト一覧読み込みは成功。ブラウザ実行・CIは未実施 |
| 視覚QA | 未実施 | 対応するブラウザ制御環境が利用できず実施不可。レスポンシブCSSの実装とビルド成功のみ |
| 実OpenAI API | 未実行 | モックHTTPでスキーマ・引用・失敗経路を検証。実キーなし |
| GitHub公開 | ソース公開 | https://github.com/remanpso2-wq/relay-desk |
| 外部ホスティング | 未実施 | 稼働中の公開デモURLはありません |
| SQLite復元 | 成功 | results/restore.json。架空データ入りDBの全テーブル件数・内容ハッシュ・integrity_check・foreign_key_checkを照合 |
| 負荷/PostgreSQL復元/第三者診断 | 未実施 | 実運用の判断材料はまだ不足 |

Starlette TestClientのhttpx利用に非推奨警告が1件。テストは成功するが、次の依存更新時に推奨クライアントへの移行を評価する。

## 受入で実際に確認すること

1. 管理者で問い合わせ登録→プレビュー→生成→編集→承認→完了→再読込。
2. 担当者では資料編集・承認ができない。
3. 資料を更新/非公開化した古い下書きが承認できない。
4. 引用本文と回答が意味的に一致し、未記載事項を創作していない（人手評価）。
5. 390px/1440px幅、キーボード、フォーカス、長文表示、エラー回復。
6. PostgreSQLでも同じ拒否ケースと二重操作を検証する。

これらの未検証項目が残っているため、v0.2は「機能拡張・SQLite検証版」と位置づける。
