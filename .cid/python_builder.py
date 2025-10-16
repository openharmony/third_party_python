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
import datetime
import platform
import tarfile
import glob
import re



# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
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
        self.LLDB_PY_DETAILED_VERSION = f"{args.lldb_py_version}_{datetime.datetime.now().strftime('%Y%m%d')}"
        self.TARGET_OS = args.target_os
        self.TARGET_ARCH = args.target_arch
        self.HOST_OS = platform.system().lower()
        self.HOST_ARCH = 'x86' if platform.machine().startswith('x86') else 'arm64'
        self.PACKAGE_NAME = "windows-x86" if args.target_os == "mingw" else f"{args.target_os}-{args.target_arch}"

class PythonBuilder:
    target_platform = ""
    patches = []


    def __init__(self, build_config) -> None:
        self.build_config = build_config
        self.repo_root = Path(build_config.REPOROOT_DIR).resolve()
        self._out_dir = Path(build_config.OUT_PATH).resolve()
        self._source_dir = self.repo_root / 'third_party' / 'python'
        self._patch_dir = self._source_dir / '.cid' / 'patches' / build_config.TARGET_OS
        self._build_dir = self._out_dir / 'python-build'
        self._deps_dir = self._out_dir / 'python-deps'
        self._install_dir = self._out_dir / 'python-install' / build_config.PACKAGE_NAME / build_config.LLDB_PY_VERSION
        self._lldb_py_version = build_config.LLDB_PY_VERSION
        self._version = build_config.LLDB_PY_DETAILED_VERSION
        version_parts = self._version.split('.')
        prebuilt_python_sub_dir = f'{build_config.HOST_OS}-{build_config.HOST_ARCH}'
        self._major_version = version_parts[0]
        self._prebuilts_path = os.path.join(self.repo_root, 'prebuilts')
        self._prebuilts_python_path = os.path.join(self._prebuilts_path, 'python', prebuilt_python_sub_dir, 'current', 'bin',
                                                  f'python{self._major_version}')
        logging.getLogger(__name__).addHandler(logging.FileHandler(self._out_dir / 'build.log'))

    @property
    def _logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    @property
    def _cc(self) -> Path:
        return Path('/usr/bin/gcc')

    @property
    def _cflags(self) -> List[str]:
        return []

    @property
    def _ldflags(self) -> List[str]:
        return []

    @property
    def _cxx(self) -> Path:
        return Path('/usr/bin/g++')

    @property
    def _strip(self) -> Path:
        return Path('/usr/bin/strip')

    @property
    def _cxxflags(self) -> List[str]:
        return self._cflags.copy()

    @property
    def _rcflags(self) -> List[str]:
        return []

    @property
    def _env(self) -> Mapping[str, str]:
        env = os.environ.copy()
        env.update({
            'CC': str(self._cc),
            'CXX': str(self._cxx),
            'STRIP': str(self._strip),
            'CFLAGS': ' '.join(self._cflags),
            'CXXFLAGS': ' '.join(self._cxxflags),
            'LDFLAGS': ' '.join(self._ldflags),
            'RCFLAGS': ' '.join(self._rcflags),
            'CPPFLAGS': ' '.join(self._cflags),
        })
        return env
    
    
    @property
    def install_dir(self) -> str:
        return str(self._install_dir)
    
    def build(self) -> None:
        self._logger.info("Starting build process...")
        self._pre_build()
        self._build()
        self._post_build()

    
    def _pre_build(self) -> None:
        self._deps_build()
        if self.build_config.TARGET_OS == "mingw":
            self._clean_patches()
            self._apply_patches()

    
    def _clean_patches(self) -> None:
        self._logger.info("Cleaning patches...")
        run_command(['git', 'reset', '--hard', 'HEAD'], cwd=self._source_dir)
        run_command(['git', 'clean', '-df', '--exclude=.cid'], cwd=self._source_dir)


    def _deps_build(self) -> None:
        self._logger.info("Starting dependency build process...")
        return


    def _apply_patches(self) -> None:
      if hasattr(self, '_patch_ignore_file') and self._patch_ignore_file.is_file():
          self._logger.warning('Patches for Python have being applied, skip patching')
          return

      if not self._patch_dir.is_dir():
          self._logger.warning('Patches are not found, skip patching')
          return
      for patch in self._patch_dir.iterdir():
          if patch.is_file():
              cmd = ['git', 'apply', str(patch)]
              self._logger.info(f"Applying patch: {patch.name}")
              run_command(cmd, cwd=self._source_dir)


    def _build(self):
        self._prepare_build_dir()
        self._configure()
        self._install()


    def _prepare_build_dir(self):
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


    def _configure(self) -> None:
        self._logger.info("Starting configuration...")
        return


    def _install(self) -> None:
        self._logger.info("Starting installation...")
        num_jobs = os.cpu_count() or 8
        cmd = ['make', f'-j{num_jobs}', 'install']
        run_command(cmd, cwd=self._build_dir)
        
    
    def _post_build(self) -> None:
        self._logger.info("Starting post-build...")
        self._prepare_package()
        self._package("")
        
    
    def _prepare_package(self) -> None:
        self._logger.info("Preparing package...")
        if self.build_config.TARGET_OS != "mingw":
            self._modify_bin_file_shebang()
            self._upgrade_pip_and_setuptools()
        self._clean_bin_dir()
        self._clean_share_dir()
        self._clean_lib_dir()
        self._copy_external_libs()
        self._strip_libs()
            
    
    
    def _clean_bin_dir(self) -> None:
        self._logger.info("ByPass Cleaning bin directory...")
    
    
    def _strip_in_place(self, file: Path) -> None:
        self._logger.info(f"Stripping file: {file}")
        cmd = [
            str(self._strip),
            '-x',
            '-S',
            str(file),
        ]
        run_command(cmd)
            

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
    
    
    def _strip_libs(self) -> None:
        so_pattern = re.compile(r'.+\.so(\.\d+)*$')
        directories = [
            self._install_dir / 'lib',
            self._install_dir / 'lib' / 'python3.11' / 'lib-dynload'
        ]
        
        for root_dir in directories:
            if not root_dir.exists():
                self._logger.warning(f"Directory not found: {root_dir}")
                continue
                
            for root, _, files in os.walk(root_dir):
                for item in files:
                    if so_pattern.match(item):
                        file_path = os.path.join(root, item)
                        self._logger.info(f"Stripping file: {file_path}")
                        self._strip_in_place(file_path)
    
    
    def _package(self, glibc_version="") -> None:
        self._logger.info("Packaging build...")
        platform = self.build_config.PACKAGE_NAME
        if glibc_version: 
            package_name = f"python-{platform}-GLIBC{glibc_version}-{self._version}.tar.gz"
        else:
            package_name = f"python-{platform}-{self._version}.tar.gz"
        archive = self._out_dir / package_name
        package_dir = self._out_dir / 'python-install'
        if archive.exists():
            self._logger.info(f"Removing existing archive: {archive}")
            archive.unlink()
        exclude_dirs = [
            "lib/python*/config-*",
            "*.pyc",
            "__pycache__",
            "*.pickle",
            "test",
            "tests",
            "tkinker",
            "turtledemo",
            "idlelib",
            "turtle.py",
            "wininst-*",
            "bdist_wininst.py",
            "*.whl"
        ]
        cmd = [
            'tar',
            '-czf',
            str(archive),
        ]
        for p in exclude_dirs:
          cmd.append("--exclude")
          cmd.append(p)
        cmd += [f.name for f in package_dir.iterdir()]
        run_command(cmd, cwd=package_dir )


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
    
    
    def _remove_dir(self, dir_path: Path) -> None:
        if dir_path.is_dir():
            self._logger.info(f"Removing directory: {dir_path}")
            shutil.rmtree(dir_path)
    
    
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
    

    def _copy_file_or_symlink_target(self, source_path, dest_dir):
        """
        拷贝文件到目标目录：
        - 若源路径是符号链接，则拷贝其指向的实际文件
        - 若源路径是普通文件，则直接拷贝该文件本身
        
        参数:
            source_path: 源文件或符号链接的路径
            dest_dir: 拷贝操作的目标目录
        """
        # Check if source path exists
        if not os.path.exists(source_path):
            self._logger.error(f"Source path does not exist: {source_path}")
            return
        
        # Determine the actual file path to copy
        if os.path.islink(source_path):
            # For symbolic links, get the target path
            actual_path = os.path.realpath(source_path)
            self._logger.info(f"Symbolic link detected, pointing to: {actual_path}")
        else:
            # For regular files, use the source path directly
            actual_path = source_path
        
        # Ensure target directory exists
        os.makedirs(dest_dir, exist_ok=True)
        
        # Perform the copy operation (preserving metadata)
        shutil.copy2(actual_path, dest_dir)
        self._logger.info(f"Successfully copied to {os.path.join(dest_dir, os.path.basename(actual_path))}")
    
    
    def _modify_bin_file_shebang(self):
        self._logger.info("Modify bin file shebang...")
        python_bin_dir = self._install_dir / 'bin'
        for file in python_bin_dir.iterdir():
            self._modify_file_shebang(file)
    

    def _modify_file_shebang(self, file_path):
        """
        修改文件中的shebang行，仅校验第一行是否以#!开头
        
        参数:
            file_path: 要修改的文件路径
        返回:
            bool: 修改成功返回True，否则返回False
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            self._logger.error(f"File not found: {file_path}")
            return False

        # 检查文件是否可读写
        if not os.access(file_path, os.R_OK | os.W_OK):
            self._logger.error(f"No read/write permission for file: {file_path}")
            return False

        try:
            # 读取文件第一行
            with open(file_path, 'r') as f:
                first_line = f.readline().rstrip('\n')  # 移除换行符

            # 只校验第一行是否以#!开头
            if not first_line.startswith('#!'):
                self._logger.info(f"File does not have a shebang line: {file_path}")
                return False
            # 检查是否需要修改
            else:
                # 读取所有内容并修改第一行
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                
                lines[0] = '#!./python3.11\n'
                
                # 写回文件
                with open(file_path, 'w') as f:
                    f.writelines(lines)
                
                self._logger.info(f"Updated shebang in: {file_path}")
                return True

        except Exception as e:
            self._logger.warning(f"Error updating shebang in {file_path}: {e}")
    
    
    def _upgrade_pip_and_setuptools(self):
        self._logger.info("Upgrade pip and setuptools...")
        pip_path = self._install_dir / 'bin' / 'pip3'
        run_command([str(pip_path), 'install', '--upgrade', 'pip', '--index-url', 'https://mirrors.huaweicloud.com/repository/pypi/simple', '--trusted-host', 'mirrors.huaweicloud.com'], cwd=self._install_dir / 'bin') 
        run_command([str(pip_path), 'install', '--upgrade', 'setuptools', '--index-url', 'https://mirrors.huaweicloud.com/repository/pypi/simple', '--trusted-host', 'mirrors.huaweicloud.com'], cwd=self._install_dir / 'bin') 
