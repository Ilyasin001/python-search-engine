from searchengine.document import Document


def test_text_joins_list_fields():
    doc = Document(id=1, fields={"title": "Stop words", "tags": ["analysis", "fundamentals"]})
    assert doc.text("title") == "Stop words"
    assert doc.text("tags") == "analysis fundamentals"
    assert doc.text("missing") == ""
