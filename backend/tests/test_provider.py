import json
import pytest
import httpx
from app import ai

SRC = [
    {
        "id": "article-a",
        "version": 1,
        "title": "配送先変更",
        "excerpt": "出荷前のみ変更できます。",
        "score": 0.7,
    }
]


def client(monkeypatch, body, status=200):
    real = httpx.Client

    def handler(req):
        p = json.loads(req.content)
        assert p["store"] is False
        assert p["text"]["format"]["strict"] is True
        assert "tools" not in p
        return httpx.Response(status, json=body)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )


def response(answer="出荷前のみ変更できます。", ids=None):
    return {
        "status": "completed",
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "answer": answer,
                                "citation_ids": ["article-a"] if ids is None else ids,
                                "needs_human": True,
                            }
                        ),
                    }
                ]
            }
        ],
    }


def test_valid_structured_response(monkeypatch):
    client(monkeypatch, response())
    result = ai.generate("配送先を変更したい", SRC, "openai")
    assert result[1] == ["article-a"]
    assert result[2] is True


@pytest.mark.parametrize("ids", [[], ["unknown-article"]])
def test_invalid_citation_rejected(monkeypatch, ids):
    client(monkeypatch, response(ids=ids))
    with pytest.raises(ValueError):
        ai.generate("質問", SRC, "openai")


def test_incomplete_response(monkeypatch):
    client(monkeypatch, {"status": "incomplete", "output": []})
    with pytest.raises(ValueError):
        ai.generate("質問", SRC, "openai")


def test_external_failure_no_fallback(monkeypatch):
    client(monkeypatch, {"error": "unavailable"}, 503)
    with pytest.raises(httpx.HTTPStatusError):
        ai.generate("質問", SRC, "openai")


def test_no_sources_skips_api(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = ai.generate("未登録の質問", [], "openai")
    assert result[0] == ""
    assert result[4] == "none"


def test_retrieval_handles_normalization_and_no_match():
    from types import SimpleNamespace

    a = SimpleNamespace(
        id="a",
        version=1,
        title="配送先住所の変更",
        body="出荷前に配送先住所を変更できます。",
    )
    assert ai.retrieve("配送先住所を変更したい", [a])[0]["id"] == "a"
    assert ai.retrieve("XYZ123", [a]) == []


def test_retrieval_finds_evidence_after_first_1600_characters():
    from types import SimpleNamespace

    article = SimpleNamespace(
        id="long",
        version=1,
        title="利用規約",
        body="一般事項の説明です。" * 200
        + "\n海外配送は現在受け付けていません。国内配送のみ対応しています。",
    )
    src = ai.retrieve("海外配送の対応について", [article])
    assert src and src[0]["offset"] > 1600
    assert "海外配送は現在受け付けていません" in src[0]["excerpt"]
