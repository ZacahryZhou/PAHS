from tool import run

def test_count_words():
    result = run("hello world from pahs")
    assert result["word_count"] == 4

if __name__ == "__main__":
    test_count_words()
    print("ok")
