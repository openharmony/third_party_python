#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2025 Huawei Device Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import List, Mapping
import binascii
import glob
import tarfile


# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)


def run_command(cmd, cwd=None, env=None):
    logger = logging.getLogger(__name__)
    try:
        logger.info(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=True)
        if result.stdout:
            logger.info(f"Command output: {result.stdout.strip()}")
        if result.stderr:
            logger.warning(f"Command error output: {result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}. Error: {e.stderr.strip()}")
        raise

class BuildConfig:
    def __init__(self, args):
        self.REPOROOT_DIR = args.repo_root
        self.OUT_PATH = args.out_path
        self.LLDB_PY_VERSION = args.lldb_py_version
        self.LLDB_PY_DETAILED_VERSION = args.lldb_py_detailed_version
        self.MINGW_TRIPLE = args.mingw_triple


class PythonBuilder:
    target_platform = ""
    patches = []


    def __init__(self, build_config) -> None:
        self.build_config = build_config
        self.repo_root = Path(build_config.REPOROOT_DIR).resolve()
        self._out_dir = Path(build_config.OUT_PATH).resolve()
        self._lldb_py_version = build_config.LLDB_PY_VERSION
        self._version = build_config.LLDB_PY_DETAILED_VERSION
        version_parts = self._version.split('.')
        self._major_version = version_parts[0]
        self._source_dir = self.repo_root / 'third_party' / 'python'
        self._patch_dir = self._source_dir / '.cid' / 'patches'
        self._prebuilts_path = os.path.join(self.repo_root, 'prebuilts')
        self._prebuilts_python_path = os.path.join(self._prebuilts_path, 'python', 'linux-x86', self._lldb_py_version, 'bin',
                                                  f'python{self._major_version}')
        self._install_dir = ""
        self._clean_patches()
        logging.getLogger(__name__).addHandler(logging.FileHandler(self._out_dir / 'build.log'))

    @property
    def _logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    @property
    def _cc(self) -> Path:
        return self._clang_toolchain_dir / 'bin' / 'clang'

    @property
    def _cflags(self) -> List[str]:
        return []

    @property
    def _ldflags(self) -> List[str]:
        return []

    @property
    def _cxx(self) -> Path:
        return self._clang_toolchain_dir / 'bin' / 'clang++'

    @property
    def _strip(self) -> Path:
        return self._clang_toolchain_dir / 'bin' / 'llvm-strip'

    @property
    def _cxxflags(self) -> List[str]:
        return self._cflags.copy()

    @property
    def _rcflags(self) -> List[str]:
        return []

    @property
    def _env(self) -> Mapping[str, str]:
        env = os.environ.copy()
        clang_bin_dir = self._clang_toolchain_dir / 'bin'

        env.update({
            'CC': str(self._cc),
            'CXX': str(self._cxx),
            'WINDRES': str(clang_bin_dir / 'llvm-windres'),
            'AR': str(clang_bin_dir / 'llvm-ar'),
            'READELF': str(clang_bin_dir / 'llvm-readelf'),
            'LD': str(clang_bin_dir / 'ld.lld'),
            'DLLTOOL': str(clang_bin_dir / 'llvm-dlltoo'),
            'RANLIB': str(clang_bin_dir / 'llvm-ranlib'),
            'STRIP': str(self._strip),
            'CFLAGS': ' '.join(self._cflags),
            'CXXFLAGS': ' '.join(self._cxxflags),
            'LDFLAGS': ' '.join(self._ldflags),
            'RCFLAGS': ' '.join(self._rcflags),
            'CPPFLAGS': ' '.join(self._cflags),
            'LIBS': '-lffi'
        })
        return env

    def _configure(self) -> None:
        self._logger.info("Starting configuration...")
        return

    def _clean_patches(self) -> None:
        self._logger.info("Cleaning patches...")
        run_command(['git', 'reset', '--hard', 'HEAD'], cwd=self._source_dir)
        run_command(['git', 'clean', '-df', '--exclude=.cid'], cwd=self._source_dir)

    def _pre_build(self) -> None:
        self._deps_build()
        self._apply_patches()

    def _apply_patches(self) -> None:
      if hasattr(self, '_patch_ignore_file') and self._patch_ignore_file.is_file():
          self._logger.warning('Patches for Python have being applied, skip patching')
          return

      if not self._patch_dir.is_dir():
          self._logger.warning('Patches are not found, skip patching')
          return

      for patch in self._patch_dir.iterdir():
          if patch.is_file() and patch.name in self.patches:
              cmd = ['git', 'apply', str(patch)]
              self._logger.info(f"Applying patch: {patch.name}")
              run_command(cmd, cwd=self._source_dir)


    def _deps_build(self) -> None:
        self._logger.info("Starting dependency build process...")
        return

    def build(self) -> None:
        self._logger.info("Starting build process...")
        self._pre_build()
        if hasattr(self, '_build_dir') and self._build_dir.exists():
            self._logger.info(f"Removing existing build directory: {self._build_dir}")
            shutil.rmtree(self._build_dir)
        if isinstance(self._install_dir, Path) and self._install_dir.exists():
            self._logger.info(f"Removing existing install directory: {self._install_dir}")
            shutil.rmtree(self._install_dir)
        if hasattr(self, '_build_dir'):
            self._build_dir.mkdir(parents=True)
        if isinstance(self._install_dir, Path):
            self._install_dir.mkdir(parents=True)
        self._configure()
        self._install()

    def _install(self) -> None:
        self._logger.info("Starting installation...")
        num_jobs = os.cpu_count() or 8
        cmd = ['make', f'-j{num_jobs}', 'install']
        run_command(cmd, cwd=self._build_dir)

    def _strip_in_place(self, file: Path) -> None:
        self._logger.info(f"Stripping file: {file}")
        cmd = [
            str(self._strip),
            str(file),
        ]
        run_command(cmd)

    def _clean_bin_dir(self) -> None:
        self._logger.info("Cleaning bin directory...")
        python_bin_dir = self._install_dir / 'bin'
        if not python_bin_dir.is_dir():
            return

        windows_suffixes = ('.exe', '.dll')
        for f in python_bin_dir.iterdir():
            if f.suffix not in windows_suffixes or f.is_symlink():
                self._logger.info(f"Removing file: {f}")
                f.unlink()
                continue
            self._strip_in_place(f)

    def _remove_dir(self, dir_path: Path) -> None:
        if dir_path.is_dir():
            self._logger.info(f"Removing directory: {dir_path}")
            shutil.rmtree(dir_path)

    def _clean_share_dir(self) -> None:
        self._logger.info("Cleaning share directory...")
        share_dir = self._install_dir / 'share'
        self._remove_dir(share_dir)

    def _clean_lib_dir(self) -> None:
        self._logger.info("Cleaning lib directory...")
        python_lib_dir = self._install_dir / 'lib'
        pkgconfig_dir = python_lib_dir / 'pkgconfig'
        self._remove_dir(pkgconfig_dir)

    def _remove_exclude(self) -> None:
        self._logger.info("Removing excluded files and directories...")
        exclude_dirs_tuple = (
            f'config-{self._major_version}',
            '__pycache__',
            'idlelib',
            'tkinter', 'turtledemo',
            'test', 'tests'
        )
        exclude_files_tuple = (
            'bdist_wininst.py',
            'turtle.py',
            '.whl',
            '.pyc', '.pickle'
        )

        for root, dirs, files in os.walk(self._install_dir / 'lib'):
            for item in dirs:
                if item.startswith(exclude_dirs_tuple):
                    self._logger.info(f"Removing directory: {os.path.join(root, item)}")
                    shutil.rmtree(os.path.join(root, item))
            for item in files:
                if item.endswith(exclude_files_tuple):
                    self._logger.info(f"Removing file: {os.path.join(root, item)}")
                    os.remove(os.path.join(root, item))

    def _copy_external_libs(self) -> None:
        self._logger.info("Copying external libraries...")
        # 定义源文件路径
        _external_libs = [self._deps_dir / 'ffi' / 'bin' / 'libffi-8.dll', self._clang_toolchain_dir / self.build_config.MINGW_TRIPLE / 'bin' / 'libssp-0.dll']
        # 定义目标目录
        target_dir = self._install_dir / 'lib' / 'python3.11' / 'lib-dynload'
        # 创建目标目录（如果不存在）
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            for lib in _external_libs :
                # 调用提取的方法拷贝 libffi-8.dll
                self._copy_file_if_exists(lib, target_dir)
        except Exception as e:
            self._logger.error(f"Error copying external libraries: {e}")

    def _copy_file_if_exists(self, src_path: Path, dest_dir: Path) -> None:
        """
        若源文件存在，则将其拷贝到目标目录，并记录相应日志；若不存在，则记录警告日志。

        :param src_path: 源文件的路径
        :param dest_dir: 目标目录的路径
        """
        if src_path.exists():
            shutil.copy2(src_path, dest_dir)
            self._logger.info(f"Copied {src_path} to {dest_dir}")
        else:
            self._logger.warning(f"{src_path} does not exist. Skipping.")

    def _is_elf_file(self, file_path: Path) -> bool:
        with open(file_path, 'rb') as f:
            magic_numbers = f.read(4)
            hex_magic_number = binascii.hexlify(magic_numbers).decode('utf-8')
            return hex_magic_number == '7f454c46'

    @property
    def install_dir(self) -> str:
        return str(self._install_dir)


class MinGWPythonBuilder(PythonBuilder):
    def __init__(self, build_config) -> None:
        super().__init__(build_config)

        self.target_platform = "x86_64-w64-mingw32"
        self.patches = [f'cpython_mingw_v{self._version}.patch']
        self._clang_toolchain_dir = Path(
            os.path.join(self._prebuilts_path, 'mingw-w64', 'ohos', 'linux-x86_64', 'clang-mingw')).resolve()
        self._mingw_install_dir = self._clang_toolchain_dir / build_config.MINGW_TRIPLE
        self._build_dir = self._out_dir / 'python-windows-build'
        self._install_dir = self._out_dir / 'python-windows-install'
        self._deps_dir = self._out_dir / 'python-windows-deps'
        # This file is used to detect whether patches are applied
        self._patch_ignore_file = self._source_dir / 'mingw_ignorefile.txt'

        for directory in (self._mingw_install_dir, self._source_dir):
            if not directory.is_dir():
                raise ValueError(f'No such directory "{directory}"')

    def _extract_libffi(self):
        """
        定位 libffi-*.tar.gz 文件，清理输出目录后，将其直接解压到 out/libffi 目录。

        Returns:
            Path: 解压后的 libffi 内部目录的路径。

        Raises:
            FileNotFoundError: 若未找到 libffi-*.tar.gz 文件。
            Exception: 若无法获取 libffi 压缩包的内部目录。
        """
        # 找到 libffi-*.tar.gz 包
        libffi_tar_gz_files = glob.glob(str(self.repo_root / 'third_party' / 'libffi' / 'libffi-*.tar.gz'))
        if not libffi_tar_gz_files:
            self._logger.error("No libffi-*.tar.gz file found in third_party/libffi directory.")
            raise FileNotFoundError("No libffi-*.tar.gz file found.")
        libffi_tar_gz = libffi_tar_gz_files[0]

        # 清理 out/libffi 目录
        libffi_extract_dir = self._out_dir / 'libffi'
        if libffi_extract_dir.exists():
            self._logger.info(f"Cleaning existing libffi directory: {libffi_extract_dir}")
            shutil.rmtree(libffi_extract_dir)
        libffi_extract_dir.mkdir(parents=True)

        # 直接解压 libffi-*.tar.gz 到 out/libffi 目录
        with tarfile.open(libffi_tar_gz, 'r:gz') as tar:
            tar.extractall(path=libffi_extract_dir)
            # 获取解压后的目录名
            members = tar.getmembers()
            if members:
                libffi_inner_dir = libffi_extract_dir / members[0].name
            else:
                self._logger.error("Failed to get inner directory of libffi tarball.")
                raise Exception("Failed to get inner directory of libffi tarball.")
        return libffi_inner_dir

    @property
    def _cflags(self) -> List[str]:
        cflags = [
            f'-target {self.target_platform}',
            f'--sysroot={self._mingw_install_dir}',
            f'-fstack-protector-strong',
            f'-I{str(self._deps_dir / "ffi" / "include")}',
            f'-nostdinc',
            f'-I{str(self._mingw_install_dir / "include")}',
            f'-I{str(self._clang_toolchain_dir / "lib" / "clang" / "15.0.4" / "include")}'
        ]
        return cflags

    @property
    def _ldflags(self) -> List[str]:
        ldflags = [
            f'--sysroot={self._mingw_install_dir}',
            f'-rtlib=compiler-rt',
            f'-target {self.target_platform}',
            f'-lucrt',
            f'-lucrtbase',
            f'-fuse-ld=lld',
            f'-L{str(self._deps_dir / "ffi" / "lib")}',
        ]
        return ldflags

    @property
    def _rcflags(self) -> List[str]:
        return [f'-I{self._mingw_install_dir}/include']

    def _deps_build(self) -> None:
        self._logger.info("Starting MinGW dependency build process...")
        # 调用提取的方法
        libffi_inner_dir = self._extract_libffi()

        env = os.environ.copy()
        env.update({
            'CC': "/bin/x86_64-w64-mingw32-gcc",
            'CXX': "/bin/x86_64-w64-mingw32-g++",
            'WINDRES': "/bin/x86_64-w64-mingw32-windres",
            'AR': "/bin/x86_64-w64-mingw32-ar",
            'READELF': "/bin/x86_64-w64-mingw32-readelf",
            'LD': "/bin/x86_64-w64-mingw32-ld",
            'DLLTOOL': "/bin/x86_64-w64-mingw32-dlltool",
            'RANLIB': "/bin/x86_64-w64-mingw32-gcc-ranlib",
            'STRIP': "/bin/x86_64-w64-mingw32-strip",
            'CFLAGS': "--sysroot=/usr/x86_64-w64-mingw32 -fstack-protector-strong",
            'CXXFLAGS': "--sysroot=/usr/x86_64-w64-mingw32 -fstack-protector-strong",
            'LDFLAGS': "--sysroot=/usr/x86_64-w64-mingw32",
            'RCFLAGS': "-I/usr/x86_64-w64-mingw32/include",
            'CPPFLAGS': "--sysroot=/usr/x86_64-w64-mingw32 -fstack-protector-strong"
        })

        configure_cmd = [
            "./configure",
            f"--prefix={self._deps_dir / 'ffi'}",
            "--enable-shared",
            "--build=x86_64-pc-linux-gnu",
            "--host=x86_64-w64-mingw32",
            "--disable-symvers",
            "--disable-docs"
        ]
        run_command(configure_cmd, env=env, cwd=libffi_inner_dir)

        # 执行 make -j16
        make_cmd = ['make', '-j16']
        run_command(make_cmd, env=env, cwd=libffi_inner_dir)

        # 执行 make install
        make_install_cmd = ['make', 'install']
        run_command(make_install_cmd, env=env, cwd=libffi_inner_dir)

    def _configure(self) -> None:
        self._logger.info("Starting MinGW configuration...")
        run_command(['autoreconf', '-vfi'], cwd=self._source_dir)
        build_platform = subprocess.check_output(
            ['./config.guess'], cwd=self._source_dir).decode().strip()
        config_flags = [
            f'--prefix={self._install_dir}',
            f'--build={build_platform}',
            f'--host={self.target_platform}',
            f'--with-build-python={self._prebuilts_python_path}',
            '--enable-shared',
            '--without-ensurepip',
            '--enable-loadable-sqlite-extensions',
            '--disable-ipv6',
            '--with-pydebug',
            '--with-system-ffi'
        ]
        cmd = [str(self._source_dir / 'configure')] + config_flags
        run_command(cmd, env=self._env, cwd=self._build_dir)

    def prepare_for_package(self) -> None:
        self._logger.info("Preparing MinGW build for packaging...")
        self._clean_bin_dir()
        self._clean_share_dir()
        self._clean_lib_dir()
        self._remove_exclude()
        self._copy_external_libs()

    def package(self) -> None:
        self._logger.info("Packaging MinGW build...")
        archive = self._out_dir / f'python-mingw-x86-{self._version}.tar.gz'
        if archive.exists():
            self._logger.info(f"Removing existing archive: {archive}")
            archive.unlink()
        cmd = [
            'tar',
            '-czf',
            str(archive),
            '--exclude=__pycache__',
            '--transform',
            f's,^,python/windows-x86/{self._lldb_py_version}/,',
        ] + [f.name for f in self._install_dir.iterdir()]
        run_command(cmd, cwd=self._install_dir)
