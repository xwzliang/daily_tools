import ctypes
import errno
import os
import sys


def move_without_overwrite(source, destination):
    """Move within a filesystem, atomically refusing an occupied destination."""
    if sys.platform == "win32":
        os.rename(source, destination)  # Windows rename refuses existing files.
        return
    if sys.platform == "darwin" or sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        src, dst = os.fsencode(source), os.fsencode(destination)
        if sys.platform == "darwin":
            result = libc.renamex_np(src, dst, 4)  # RENAME_EXCL
        elif hasattr(libc, "renameat2"):
            result = libc.renameat2(-100, src, -100, dst, 1)  # AT_FDCWD, RENAME_NOREPLACE
        else:
            result = -1
            ctypes.set_errno(errno.ENOSYS)
        if result == 0:
            return
        code = ctypes.get_errno()
        if code not in (errno.ENOSYS, errno.ENOTSUP, errno.EINVAL):
            raise OSError(code, os.strerror(code), str(destination))
    os.link(source, destination, follow_symlinks=False)
    os.unlink(source)
