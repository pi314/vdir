import shutil
import subprocess

from . import logger
from .utils import *
from .vdpath import *


def gen_tmp_file_name(path, postfix='.vdtmp'):
    import time
    now = time.time()
    tmp_file_name = '{orig_path}{postfix}.[{timestamp}][{getpid}]'.format(
            orig_path=path,
            postfix=postfix,
            timestamp=now,
            getpid=os.getpid(),
            )
    return VDPath(tmp_file_name)


def mkdirs(path, quiet=False):
    try:
        if not path.exists:
            if not quiet:
                logger.cmd(['mkdir', '-p', path.path])
            path.mkdir()
    except:
        return


def rmdir_p(path):
    if isinstance(path, VDPath):
        path = path.path

    try:
        cwd = Path.cwd().resolve()
        for probe in path.resolve().parents:
            # Delete .DS_Store if present
            try:
                (probe / '.DS_Store').unlink()
            except:
                pass

            if probe == cwd:
                # dont delete cwd
                return True

            if not probe.is_dir():
                # something weird happen
                return

            for child in probe.iterdir():
                # if probe/ is not empty, return
                return True

            # probe/ is empty, delete it
            logger.cmd(['rmdir', probe])
            probe.rmdir()
    except:
        return


class CopyCommand:
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst
        self.res = None

    def __call__(self):
        try:
            if self.dst.exists:
                raise FileExistsError(self.dst)

            mkdirs(self.dst.parent)
            self.echo()
            if self.src.isdir:
                shutil.copytree(self.src.path, self.dst.path,
                                symlinks=True,
                                copy_function=shutil.copy,
                                ignore_dangling_symlinks=True)
            else:
                shutil.copy(self.src.path, self.dst.path, follow_symlinks=False)
            self.res = True

        except Exception as e:
            logger.error(e)
            self.res = False

        return self.res

    def echo(self):
        if self.src.isdir:
            cmd = ['cp', '-r', self.src.path, self.dst.path]
        else:
            cmd = ['cp', self.src.path, self.dst.path]
        logger.cmd(cmd, res=self.res)


class MoveCommand:
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst
        self.res = None

    def __call__(self):
        try:
            mkdirs(self.dst.parent)
            self.echo()
            self.src.rename(self.dst)
            rmdir_p(self.src)
            self.res = True

        except Exception as e:
            logger.error(e)
            self.res = False

        return self.res

    def echo(self):
        logger.cmd(['mv', self.src.path, self.dst.path], res=self.res)


class DeleteCommand:
    def __init__(self, who):
        self.who = who
        self.res = None

    def __call__(self):
        try:
            self.echo()
            if self.who.isdir:
                shutil.rmtree(self.who.path)
            else:
                self.who.unlink()
            rmdir_p(self.who)
            self.res = True

        except Exception as e:
            if not self.who.exists:
                # Delete failed but it's gone so ok
                logger.warning(e)
            else:
                logger.error(e)
                self.res = False

        return self.res

    def echo(self):
        if self.who.isdir:
            cmd = ['rm', '-r', self.who.path]
        else:
            cmd = ['rm', self.who.path]
        logger.cmd(cmd, res=self.res)


class RelinkCommand:
    def __init__(self, lnk, ref):
        self.lnk = lnk
        self.ref = ref
        self.res = None

    def __call__(self):
        try:
            self.echo()
            if self.lnk.islink:
                self.lnk.unlink()
            self.lnk.symlink_to(self.ref)
            self.res = True

        except Exception as e:
            logger.error(e)
            self.res = False

        return self.res

    def echo(self):
        if self.lnk.islink:
            logger.cmd(['rm', self.lnk.path], res=self.res)
        logger.cmd(['ln', '-s', self.ref.path, self.lnk.path], res=self.res)


class CompressCommand:
    def __init__(self, src, dst, keep=True):
        self.src = src
        self.dst = dst
        self.keep = keep
        self.res = None
        self.cmd = ['tar', 'cvf', self.dst.path, self.src.path]
        self.p = None

    def __call__(self):
        try:
            if self.dst.exists:
                raise FileExistsError(self.dst.path)

            mkdirs(self.dst.parent)
            self.echo()
            self.p = iroiro.run(self.cmd, stdin=False, stdout=False, stderr=False)

            if self.p.returncode != 0:
                return False

            if not self.keep:
                return DeleteCommand(self.src)()

        except Exception as e:
            logger.error(e)
            self.res = False

        return self.p.returncode == 0

    def echo(self):
        logger.cmd(self.cmd, res=self.res)


class UncompressCommand:
    def __init__(self, src, dst, keep=True):
        self.src = src
        self.dst = dst
        self.keep = keep
        self.res = None
        self.cmd = ['tar', 'xvf', self.src.path, '-C', self.dst.path]

        self.p = None

    def __call__(self):
        try:
            if self.dst.exists:
                raise FileExistsError(self.dst.path)

            mkdirs(self.dst, quiet=True)
            self.echo()
            self.p = iroiro.run(self.cmd, stdin=False, stdout=False, stderr=False)

            if self.p.returncode != 0:
                return False

            ls = [f for f in self.dst.listdir(True) if f.name != '.DS_Store']
            if len(ls) == 1 and ls[0].name == self.dst.name:
                tmpdir = gen_tmp_file_name(self.dst)
                MoveCommand(ls[0], tmpdir)()
                DeleteCommand(self.dst)
                MoveCommand(tmpdir, self.dst)()

            if not self.keep:
                return DeleteCommand(self.src)()

            self.res = True

        except Exception as e:
            logger.error(e)
            self.res = False

        return self.res

    def echo(self):
        logger.cmd(['mkdir', '-p', self.dst.path])
        logger.cmd(self.cmd, res=self.res)
