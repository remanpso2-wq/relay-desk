"""Small, fixed retrieval regression set; not a real-LLM quality evaluation."""

from types import SimpleNamespace
import pytest
from app.ai import retrieve

ARTICLES = [
    SimpleNamespace(
        id="shipping",
        version=1,
        title="配送先住所の変更",
        body="配送先住所の変更は、出荷準備前の注文に限り受け付けます。注文番号と新しい住所を確認してください。",
    ),
    SimpleNamespace(
        id="invoice",
        version=1,
        title="請求書・領収書の発行",
        body="請求書はマイページの注文履歴からPDFでダウンロードできます。宛名の修正は未発行の場合に限り可能です。",
    ),
    SimpleNamespace(
        id="password",
        version=1,
        title="パスワードを忘れた場合",
        body="ログイン画面からパスワードを再設定できます。メールが届かない場合は迷惑メールフォルダをご確認ください。",
    ),
]
CASES = [
    ("配送先住所を変更したい", "shipping"),
    ("出荷準備前の注文の住所変更", "shipping"),
    ("請求書をダウンロードしたい", "invoice"),
    ("領収書の発行方法", "invoice"),
    ("パスワードを忘れました", "password"),
    ("再設定メールが届かない", "password"),
    ("ZXQ999@", None),
]


@pytest.mark.parametrize("question,expected", CASES)
def test_top_result(question, expected):
    found = retrieve(question, ARTICLES)
    assert (found[0]["id"] if found else None) == expected
