from __future__ import annotations

from pathlib import Path

import pytest

from umanager.backend.filesystem import (
    CopyOptions,
    DeleteOptions,
    FileSystemService,
    ListOptions,
)


@pytest.fixture
def service() -> FileSystemService:
    """Create FileSystemService instance"""
    return FileSystemService()


def _set_windows_hidden(path: Path) -> None:
    """Mark file as hidden on Windows using FILE_ATTRIBUTE_HIDDEN."""
    try:
        import win32api  # type: ignore[import-not-found]
        import win32file  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"pywin32 not available: {exc}")

    attrs = win32api.GetFileAttributes(str(path))
    win32api.SetFileAttributes(str(path), attrs | win32file.FILE_ATTRIBUTE_HIDDEN)


class TestListDirectory:
    def test_list_directory_empty(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test listing empty directory"""
        entries = service.list_directory(tmp_path)
        assert entries == []

    def test_list_directory_with_files(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test listing directory with files"""
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()

        entries = service.list_directory(tmp_path)
        assert len(entries) == 2
        assert entries[0].name in ("file1.txt", "file2.txt")
        assert all(e.is_file for e in entries)

    def test_list_directory_with_subdirs(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test listing directory with subdirectories"""
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir2").mkdir()

        entries = service.list_directory(tmp_path)
        assert len(entries) == 2
        assert all(e.is_dir for e in entries)

    def test_list_directory_exclude_hidden(
        self, service: FileSystemService, tmp_path: Path
    ) -> None:
        """Test excluding hidden files"""
        (tmp_path / "visible.txt").touch()
        hidden = tmp_path / "hidden.txt"
        hidden.touch()
        _set_windows_hidden(hidden)

        entries = service.list_directory(tmp_path)
        assert len(entries) == 1
        assert entries[0].name == "visible.txt"

    def test_list_directory_include_hidden(
        self, service: FileSystemService, tmp_path: Path
    ) -> None:
        """Test including hidden files"""
        (tmp_path / "visible.txt").touch()
        hidden = tmp_path / "hidden.txt"
        hidden.touch()
        _set_windows_hidden(hidden)

        entries = service.list_directory(tmp_path, ListOptions(include_hidden=True))
        assert len(entries) == 2

    def test_list_directory_not_exist(self, service: FileSystemService) -> None:
        """Test listing non-existent directory"""
        with pytest.raises(FileNotFoundError):
            service.list_directory("/nonexistent/path")

    def test_list_directory_not_a_directory(
        self, service: FileSystemService, tmp_path: Path
    ) -> None:
        """Test listing a file instead of directory"""
        file_path = tmp_path / "file.txt"
        file_path.touch()

        with pytest.raises(NotADirectoryError):
            service.list_directory(file_path)

    def test_list_directory_sorted(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that returned entries are sorted by name"""
        (tmp_path / "c.txt").touch()
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()

        entries = service.list_directory(tmp_path)
        names = [e.name for e in entries]
        assert names == ["a.txt", "b.txt", "c.txt"]


class TestTouchFile:
    def test_touch_file_creates_file(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test creating a file"""
        file_path = tmp_path / "test.txt"
        result = service.touch_file(file_path)

        assert file_path.exists()
        assert result == file_path

    def test_touch_file_exist_ok_true(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that exist_ok=True does not overwrite existing file"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("original content")

        service.touch_file(file_path, exist_ok=True)

        assert file_path.read_text() == "original content"

    def test_touch_file_exist_ok_false(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that exist_ok=False raises exception"""
        file_path = tmp_path / "test.txt"
        file_path.touch()

        with pytest.raises(FileExistsError):
            service.touch_file(file_path, exist_ok=False)

    def test_touch_file_with_parents(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test creating parent directories"""
        file_path = tmp_path / "subdir1" / "subdir2" / "test.txt"
        result = service.touch_file(file_path, parents=True)

        assert file_path.exists()
        assert result == file_path

    def test_touch_file_without_parents(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that missing parents raise exception"""
        file_path = tmp_path / "nonexistent" / "test.txt"

        with pytest.raises(FileNotFoundError):
            service.touch_file(file_path, parents=False)


class TestCopyPath:
    def test_copy_file(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test copying a file"""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("content")

        result = service.copy_path(src, dst)

        assert dst.exists()
        assert dst.read_text() == "content"
        assert result == dst

    def test_copy_file_overwrite_false(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that overwrite=False raises exception"""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("source content")
        dst.write_text("dest content")

        with pytest.raises(FileExistsError):
            service.copy_path(src, dst, options=CopyOptions(overwrite=False))

    def test_copy_file_overwrite_true(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that overwrite=True overwrites file"""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("source content")
        dst.write_text("dest content")

        service.copy_path(src, dst, options=CopyOptions(overwrite=True))

        assert dst.read_text() == "source content"

    def test_copy_directory_recursive(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test recursive copying directory"""
        src_dir = tmp_path / "source_dir"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1")
        (src_dir / "subdir").mkdir()
        (src_dir / "subdir" / "file2.txt").write_text("content2")

        dst_dir = tmp_path / "dest_dir"
        service.copy_path(src_dir, dst_dir, options=CopyOptions(recursive=True))

        assert (dst_dir / "file1.txt").read_text() == "content1"
        assert (dst_dir / "subdir" / "file2.txt").read_text() == "content2"

    def test_copy_directory_non_recursive(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that recursive=False raises exception"""
        src_dir = tmp_path / "source_dir"
        src_dir.mkdir()
        dst_dir = tmp_path / "dest_dir"

        with pytest.raises(IsADirectoryError):
            service.copy_path(src_dir, dst_dir, options=CopyOptions(recursive=False))

    def test_copy_directory_merge(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test merging directories when copying"""
        src_dir = tmp_path / "source_dir"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1")

        dst_dir = tmp_path / "dest_dir"
        dst_dir.mkdir()
        (dst_dir / "file2.txt").write_text("content2")

        service.copy_path(src_dir, dst_dir, options=CopyOptions(recursive=True))

        assert (dst_dir / "file1.txt").read_text() == "content1"
        assert (dst_dir / "file2.txt").read_text() == "content2"

    def test_copy_source_not_exist(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that non-existent source raises exception"""
        src = tmp_path / "nonexistent.txt"
        dst = tmp_path / "dest.txt"

        with pytest.raises(FileNotFoundError):
            service.copy_path(src, dst)

    def test_copy_creates_parent_dir(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that copying creates parent directories"""
        src = tmp_path / "source.txt"
        src.write_text("content")
        dst = tmp_path / "subdir1" / "subdir2" / "dest.txt"

        service.copy_path(src, dst)

        assert dst.exists()
        assert dst.read_text() == "content"


class TestMovePath:
    def test_move_file(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test moving a file"""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("content")

        result = service.move_path(src, dst)

        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "content"
        assert result == dst

    def test_move_file_overwrite_false(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that overwrite=False raises exception"""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("source content")
        dst.write_text("dest content")

        with pytest.raises(FileExistsError):
            service.move_path(src, dst, overwrite=False)

    def test_move_file_overwrite_true(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that overwrite=True overwrites file"""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("source content")
        dst.write_text("dest content")

        service.move_path(src, dst, overwrite=True)

        assert not src.exists()
        assert dst.read_text() == "source content"

    def test_move_directory_merge(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test merging directories when moving"""
        src_dir = tmp_path / "source_dir"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1")

        dst_dir = tmp_path / "dest_dir"
        dst_dir.mkdir()
        (dst_dir / "file2.txt").write_text("content2")

        service.move_path(src_dir, dst_dir)

        assert not src_dir.exists()
        assert (dst_dir / "file1.txt").read_text() == "content1"
        assert (dst_dir / "file2.txt").read_text() == "content2"

    def test_move_source_not_exist(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that non-existent source raises exception"""
        src = tmp_path / "nonexistent.txt"
        dst = tmp_path / "dest.txt"

        with pytest.raises(FileNotFoundError):
            service.move_path(src, dst)

    def test_move_creates_parent_dir(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that moving creates parent directories"""
        src = tmp_path / "source.txt"
        src.write_text("content")
        dst = tmp_path / "subdir1" / "subdir2" / "dest.txt"

        service.move_path(src, dst)

        assert dst.exists()
        assert dst.read_text() == "content"


class TestRename:
    def test_rename_file(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test renaming a file"""
        src = tmp_path / "old_name.txt"
        src.write_text("content")

        result = service.rename(src, "new_name.txt")

        assert not src.exists()
        assert (tmp_path / "new_name.txt").exists()
        assert result == tmp_path / "new_name.txt"

    def test_rename_overwrite_false(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that overwrite=False raises exception"""
        src = tmp_path / "file1.txt"
        dst = tmp_path / "file2.txt"
        src.write_text("content1")
        dst.write_text("content2")

        with pytest.raises(FileExistsError):
            service.rename(src, "file2.txt", overwrite=False)

    def test_rename_overwrite_true(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test that overwrite=True overwrites"""
        src = tmp_path / "file1.txt"
        dst = tmp_path / "file2.txt"
        src.write_text("content1")
        dst.write_text("content2")

        service.rename(src, "file2.txt", overwrite=True)

        assert not src.exists()
        assert dst.read_text() == "content1"


class TestDelete:
    def test_delete_file(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test deleting a file"""
        file_path = tmp_path / "test.txt"
        file_path.touch()

        service.delete(file_path)

        assert not file_path.exists()

    def test_delete_directory_recursive(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test recursive deletion of directory"""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()
        (dir_path / "file.txt").touch()
        (dir_path / "subdir").mkdir()

        service.delete(dir_path, options=DeleteOptions(recursive=True))

        assert not dir_path.exists()

    def test_delete_directory_non_recursive(
        self, service: FileSystemService, tmp_path: Path
    ) -> None:
        """Test that recursive=False raises exception"""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()

        with pytest.raises(IsADirectoryError):
            service.delete(dir_path, options=DeleteOptions(recursive=False))

    def test_delete_nonexistent_force_false(
        self, service: FileSystemService, tmp_path: Path
    ) -> None:
        """Test that deleting non-existent path with force=False raises exception"""
        file_path = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            service.delete(file_path, options=DeleteOptions(force=False))

    def test_delete_nonexistent_force_true(
        self, service: FileSystemService, tmp_path: Path
    ) -> None:
        """Test that deleting non-existent path with force=True succeeds"""
        file_path = tmp_path / "nonexistent.txt"

        service.delete(file_path, options=DeleteOptions(force=True))
        # Should not raise exception


class TestPathExists:
    def test_path_exists_file(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test checking file exists"""
        file_path = tmp_path / "test.txt"
        file_path.touch()

        assert service.path_exists(file_path)

    def test_path_exists_directory(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test checking directory exists"""
        assert service.path_exists(tmp_path)

    def test_path_not_exists(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test checking non-existent path"""
        file_path = tmp_path / "nonexistent.txt"

        assert not service.path_exists(file_path)


class TestFileEntry:
    def test_file_entry_attributes(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test FileEntry attributes"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        entries = service.list_directory(tmp_path)
        entry = entries[0]

        assert entry.name == "test.txt"
        assert entry.is_file
        assert not entry.is_dir
        assert entry.size == 7
        assert entry.mtime is not None

    def test_directory_entry_attributes(self, service: FileSystemService, tmp_path: Path) -> None:
        """Test directory FileEntry attributes"""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()

        entries = service.list_directory(tmp_path)
        entry = entries[0]

        assert entry.name == "test_dir"
        assert entry.is_dir
        assert not entry.is_file
        assert entry.size == 0
