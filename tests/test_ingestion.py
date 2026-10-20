from app.ingestion import chunk_text


def test_chunk_text_respects_size_and_overlap() -> None:
    text = " ".join(f"This is sentence number {i} about company policy." for i in range(100))
    size, overlap = 200, 50

    chunks = chunk_text(text, size, overlap)

    assert len(chunks) > 1
    assert all(len(chunk) <= size for chunk in chunks)
    # Each chunk should start with text repeated from the end of the previous chunk.
    for previous, current in zip(chunks, chunks[1:]):
        assert current[:10] in previous[-overlap:]
    assert chunks[0].startswith("This is sentence number 0")
    assert chunks[-1].endswith("number 99 about company policy.")
