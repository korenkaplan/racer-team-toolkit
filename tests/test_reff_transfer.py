from pathlib import Path

from racer_team_toolkit.reff_extractor.transfer import (
    remove_temporary_directory,
)


def test_remove_temporary_directory_deletes_ds_store_only(
    tmp_path: Path,
) -> None:
    """A staging folder containing only .DS_Store is removed completely."""

    records_dir = tmp_path / "Records"
    records_dir.mkdir()

    (records_dir / ".DS_Store").write_text(
        "finder metadata",
        encoding="utf-8",
    )

    remove_temporary_directory(
        str(records_dir),
    )

    assert not records_dir.exists()


def test_remove_temporary_directory_deletes_other_hidden_files_only(
    tmp_path: Path,
) -> None:
    """A staging folder containing only hidden files is removed completely."""

    videos_dir = tmp_path / "Screen-Videos"
    videos_dir.mkdir()

    (videos_dir / ".hidden_file").write_text(
        "temporary metadata",
        encoding="utf-8",
    )

    remove_temporary_directory(
        str(videos_dir),
    )

    assert not videos_dir.exists()


def test_remove_temporary_directory_preserves_real_reff(
    tmp_path: Path,
) -> None:
    """A staging folder with a real REFF is preserved."""

    records_dir = tmp_path / "Records"
    records_dir.mkdir()

    reff_file = records_dir / "flight.reff"
    reff_file.write_bytes(
        b"real reff data",
    )

    remove_temporary_directory(
        str(records_dir),
    )

    assert records_dir.is_dir()
    assert reff_file.is_file()


def test_remove_temporary_directory_preserves_real_video(
    tmp_path: Path,
) -> None:
    """A staging folder with a real video is preserved."""

    videos_dir = tmp_path / "Screen-Videos"
    videos_dir.mkdir()

    video_file = videos_dir / "screen_recording.mp4"
    video_file.write_bytes(
        b"real video data",
    )

    remove_temporary_directory(
        str(videos_dir),
    )

    assert videos_dir.is_dir()
    assert video_file.is_file()
