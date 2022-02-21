import os
import re
try:
    import xbmcvfs as fvs
except ImportError:
    fvs = None


class Path(str):

    def __new__(cls, *args, **kwargs):
        return str.__new__(cls, os.path.join(*args), **kwargs)

    def __repr__(self):
        return 'Path({})'.format(str.__repr__(self))

    def __add__(self, other):
        return Path(str.__add__(self, other))

    def __mul__(self, other):
        return Path(str.__mul__(self, other))

    def __rmul__(self, other):
        return Path(str.__rmul__(self, other))

    def __mod__(self, other):
        return Path(str.__mod__(self, other))

    def __rmod__(self, other):
        return Path(str.__rmod__(self, other))

    def __fspath__(self):
        print('__fspath__ called')
        return str(self)

    def __truediv__(self, other):
        """
        Join two or more pathname components, inserting '/' as needed.
        If any component is an absolute path, all previous path components
        will be discarded.  An empty last part will result in a path that
        ends with a separator.
        """
        return Path(os.path.join(self, other))

    def __rtruediv__(self, other):
        """See: __truediv__()."""
        return Path(os.path.join(self, other))

    def joinpath(self, *other):
        """Calling this method is equivalent to combining the path with each of the other arguments in turn."""
        return Path(os.path.join(self, *other))

    @property
    def drive(self):
        """A string representing the drive letter or name, if any."""
        return os.path.splitdrive(self)[0]

    @property
    def root(self):
        """A string representing the (local or global) root, if any."""
        # TODO: add handle "//path" and r"\\host\share"
        path = os.path.splitdrive(self)[1]
        return os.path.sep if os.path.isabs(path) else ''

    @property
    def anchor(self):
        """The concatenation of the drive and root."""
        return self.drive + self.root

    @property
    def parents(self):
        """An immutable sequence providing access to the logical ancestors of the path."""
        return tuple(p or '/' for p in os.path.normpath(self).split(os.path.sep))

    @property
    def parent(self):
        """The logical parent of the path."""
        return Path(os.path.dirname(self))

    @property
    def name(self):
        """A string representing the final path component, excluding the drive and root, if any."""
        return os.path.basename(self)

    @property
    def suffix(self):
        """The file extension of the final component, if any."""
        return os.path.splitext(self)[-1]

    @property
    def suffixes(self):
        """A list of the path’s file extensions."""
        return re.findall(r'(?<=.)[.][^/.]*', os.path.basename(self))

    @property
    def stem(self):
        """The final path component, without its suffix."""
        return os.path.splitext(os.path.basename(self))[0]

    def is_absolute(self):
        """Return whether the path is absolute or not. A path is considered absolute
        if it has both a root and (if the flavour allows) a drive."""
        return os.path.isabs(self)

    def is_relative_to(self, *other):
        """Return whether or not this path is relative to the other path."""
        if not other:
            raise TypeError("need at least one argument")
        try:
            all(os.path.commonpath(self, p) for p in other)
        except ValueError:
            return False

    def relative_to(self, *other):
        """Compute a version of this path relative to the path represented by other.
        If it’s impossible, ValueError is raised."""
        def rel(p):
            p = os.path.relpath(self, p)
            if p.startswith('..' + os.path.sep):
                raise ValueError("{!r} is not in the subpath of {!r}"
                                 " OR one path is relative and the other is absolute."
                                 .format(str(self), str(p)))
        if not other:
            raise TypeError("need at least one argument")
        return Path(min(rel(self, p) for p in other))

    def with_name(self, name):
        """Return a new path with the name changed. If the original path doesn’t have a name, ValueError is raised."""
        path, old = os.path.split(self)
        if not old:
            raise ValueError("%r has an empty name" % (self,))
        return Path(os.path.join(path, name))

    def with_stem(self, stem):
        """Return a new path with the stem changed. If the original path doesn’t have a name, ValueError is raised."""
        path, old = os.path.split(self)
        if not old:
            raise ValueError("%r has an empty name" % (self,))
        old, ext = os.path.splitext(old)
        return Path(os.path.join(path, stem + ext))

    def with_suffix(self, suffix):
        """Return a new path with the suffix changed. If the original path doesn’t have a suffix,
        the new suffix is appended instead. If the suffix is an empty string, the original suffix is removed."""
        if suffix and not suffix.startswith('.') or suffix == '.':
            raise ValueError("Invalid suffix %r" % (suffix,))
        if not os.path.split(self)[-1]:
            raise ValueError("%r has an empty name" % (self,))
        path, old = os.path.splitext(self)
        return Path(path + suffix)

    @classmethod
    def cwd(cls):
        """
        Return a new path pointing to the current working directory
        (as returned by os.getcwd()).
        """
        return Path(os.os.getcwd())

    @classmethod
    def home(cls):
        """
        Return a new path pointing to the user's home directory (as
        returned by os.path.expanduser('~')).
        """
        return Path(os.path.expanduser('~'))

    def exists(self):
        """Whether the path points to an existing file or directory."""
        if fvs is None:
            return os.path.exists(self)
        return fvs.exists(self)

    def is_dir(self):
        """
        Return True if the path points to a directory (or a symbolic link pointing to a directory),
        False if it points to another kind of file.

        False is also returned if the path doesn’t exist or is a broken symlink;
        other errors (such as permission errors) are propagated.
        """
        # xbmcvfs does not handle this
        return os.path.isdir()

    def is_file(self):
        """
        Return True if the path points to a regular file (or a symbolic link pointing to a regular file),
        False if it points to another kind of file.

        False is also returned if the path doesn’t exist or is a broken symlink;
        other errors (such as permission errors) are propagated.
        """
        # xbmcvfs does not handle this
        return os.path.isfile()

    def is_symlink(self):
        """
        Return True if the path points to a symbolic link, False otherwise.

        False is also returned if the path doesn’t exist;
        other errors (such as permission errors) are propagated.
        """
        # xbmcvfs does not handle this
        return os.path.islink()

    def resolve(self, strict=False):
        """
        Make the path absolute, resolving any symlinks. A new path object is returned.

        If the path doesn’t exist and strict is True, FileNotFoundError is raised. If strict is False,
        the path is resolved as far as possible and any remainder is appended without checking whether
        it exists. If an infinite loop is encountered along the resolution path, RuntimeError is raised.
        """
        try:
            return Path(os.path.realpath(self))
        except FileNotFoundError:
            if strict:
                raise
            return Path(os.path.abspath(self))

    def mkdir(self, mode=511, parents=False, exist_ok=False):
        """
        Create a new directory at this given path. If mode is given, it is combined with the process’ umask value
        to determine the file mode and access flags. If the path already exists, `FileExistsError` is raised.

        If `parents` is true, any missing parents of this path are created as needed; they are created with the default
        permissions without taking mode into account (mimicking the POSIX mkdir -p command).

        If `parents` is false (the default), a missing parent raises FileNotFoundError.

        If `exist_ok` is false (the default), FileExistsError is raised if the target directory already exists.

        If `exist_ok` is true, FileExistsError exceptions will be ignored
        (same behavior as the POSIX mkdir -p command),
        but only if the last path component is not an existing non-directory file.
        """
        if fvs is None:
            if parents:
                os.makedirs(self, mode, exist_ok=exist_ok)
            else:
                try:
                    os.makedir(self, mode)
                except FileExistsError:
                    if not exist_ok:
                        raise
        else:
            result = fvs.mkdirs(self) if parents else fvs.mkdir(self)
            if not result and (not exist_ok or not self.exists()):
                raise IOError('Can not create folder {!r}'.format(str(self)))

    def rmdir(self):
        """Remove this directory. The directory must be empty."""
        if fvs is None:
            os.rmdir(self)
        else:
            fvs.rmdir(self)

    def rename(self, target):
        """
        Rename this file or directory to the given `target`, and return a new Path instance pointing to `target`.
        On Unix, if `target` exists and is a file, it will be replaced silently if the user has permission.
        `target` can be either a string or another path object.
        """
        if fvs is None:
            os.rename(self, target)
        else:
            if not fvs.rename(self, target):
                raise IOError('Can not reanme {!r} to {!r}'.format(str(self), str(target)))

    def unlink(self, missing_ok=False):
        """
        Remove this file or symbolic link. If the path points to a directory, use `Path.rmdir()` instead.

        If `missing_ok` is false (the default), `FileNotFoundError` is raised if the path does not exist.

        If `missing_ok` is true, `FileNotFoundError` exceptions will be ignored
        (same behavior as the POSIX rm -f command).
        """
        if fvs is None:
            os.rmdir(self)
        else:
            if not fvs.remove(self) and (not missing_ok or self.exists()):
                raise IOError('Can not remove {!r}'.format(str(self)))

    # TODO: maybe add xbmcvfs sepcific functions: copy(), listdir()?


if __name__ == '__main__':
    class P:
        def __fspath__(self):
            return 'xyz'

    p = Path('a/b/c')
    print(type(p), p, repr(p), p.parent, p.name, p.parents)
    p = Path('a', 'b', 'c')
    print(type(p), p, repr(p))
    p = p / 'd'
    print(type(p), p)
    p /= 'e'
    print(type(p), p)
    p = p + 'x'
    print(type(p), p)
    p += 'y'
    print(type(p), p)
    p *= 2
    print(type(p), p)
