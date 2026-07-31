"""End-to-end CLI tests with all network access mocked."""
import pytest

from yt_transcribe import cli, fetcher, writer
from yt_transcribe.fetcher import TranscriptError

GOOD_ID = "aaaaaaaaaaa"
BAD_ID = "bbbbbbbbbbb"


@pytest.fixture
def fake_network(monkeypatch):
    calls = {"languages": None}

    def fake_fetch(video_id, languages=("en",), api=None):
        calls["languages"] = list(languages)
        if video_id == BAD_ID:
            raise TranscriptError("captions disabled")
        return ["Hello world.", "More text here."]

    monkeypatch.setattr(fetcher, "fetch_transcript", fake_fetch)
    monkeypatch.setattr(writer, "fetch_title", lambda video_id: f"Video {video_id}")
    return calls


def test_single_video_saved(tmp_path, capsys, fake_network):
    out = tmp_path / "out"
    exit_code = cli.main([GOOD_ID, "-o", str(out)])
    assert exit_code == 0
    files = list(out.glob("*.txt"))
    assert len(files) == 1
    assert files[0].name == f"Video {GOOD_ID}_{GOOD_ID}.txt"
    assert files[0].read_text(encoding="utf-8") == "Hello world. More text here.\n"
    assert "1 saved, 0 skipped, 0 failed" in capsys.readouterr().out


def test_mixed_batch_isolates_failures(tmp_path, capsys, fake_network):
    out = tmp_path / "out"
    exit_code = cli.main([GOOD_ID, "@@invalid@@", BAD_ID, "-o", str(out)])
    assert exit_code == 1
    assert len(list(out.glob("*.txt"))) == 1
    output = capsys.readouterr().out
    assert "1 saved, 0 skipped, 2 failed" in output
    assert "invalid URL or video ID" in output
    assert "captions disabled" in output


def test_no_input_is_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2


def test_missing_list_file_is_usage_error(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["-f", str(tmp_path / "nope.txt")])
    assert excinfo.value.code == 2


def test_list_file_and_positional_combined(tmp_path, fake_network):
    listfile = tmp_path / "videos.txt"
    listfile.write_text(f"# comment\n\n{GOOD_ID}\n", encoding="utf-8")
    out = tmp_path / "out"
    exit_code = cli.main(["ccccccccccc", "-f", str(listfile), "-o", str(out)])
    assert exit_code == 0
    assert len(list(out.glob("*.txt"))) == 2


def test_rerun_skips_existing_and_force_overwrites(tmp_path, capsys, fake_network, monkeypatch):
    out = tmp_path / "out"
    assert cli.main([GOOD_ID, "-o", str(out)]) == 0
    saved = next(out.glob("*.txt"))

    def changed_fetch(video_id, languages=("en",), api=None):
        return ["Changed text."]
    monkeypatch.setattr(fetcher, "fetch_transcript", changed_fetch)

    # second run: file exists -> skipped, content untouched, still exit 0
    assert cli.main([GOOD_ID, "-o", str(out)]) == 0
    assert "1 skipped" in capsys.readouterr().out
    assert saved.read_text(encoding="utf-8") == "Hello world. More text here.\n"

    # --force overwrites
    assert cli.main([GOOD_ID, "-o", str(out), "--force"]) == 0
    assert saved.read_text(encoding="utf-8") == "Changed text.\n"


def test_lang_flag_passes_priority_list(tmp_path, fake_network):
    cli.main([GOOD_ID, "-o", str(tmp_path / "out"), "--lang", "ru,en"])
    assert fake_network["languages"] == ["ru", "en"]
