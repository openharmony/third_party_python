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


import os
from pathlib import Path
import subprocess
from typing import List, Mapping
from python_builder import PythonBuilder, run_command

class MinGWPythonBuilder(PythonBuilder):
    def __init__(self, build_config) -> None:
        super().__init__(build_config)

        self.target_platform = "x86_64-w64-mingw32"
        self._clang_toolchain_dir = Path(
            os.path.join(self._prebuilts_path, 'mingw-w64', 'ohos', 'linux-x86_64', 'clang-mingw')).resolve()
        self._mingw_install_dir = self._clang_toolchain_dir / self.target_platform 
        for directory in (self._mingw_install_dir, self._source_dir):
            if not directory.is_dir():
                raise ValueError(f'No such directory "{directory}"')

    @property
    def _env(self) -> Mapping[str, str]:
        env = os.environ.copy()
        toolchain_bin_dir = self._clang_toolchain_dir / 'bin'
        env.update({
            'CC': str(self._cc),
            'CXX': str(self._cxx),
            'WINDRES': str(toolchain_bin_dir / 'llvm-windres'),
            'AR': str(toolchain_bin_dir / 'llvm-ar'),
            'READELF': str(toolchain_bin_dir / 'llvm-readelf'),
            'LD': str(toolchain_bin_dir / 'ld.lld'),
            'DLLTOOL': str(toolchain_bin_dir / 'llvm-dlltoo'),
            'RANLIB': str(toolchain_bin_dir / 'llvm-ranlib'),
            'STRIP': str(self._strip),
            'CFLAGS': ' '.join(self._cflags),
            'CXXFLAGS': ' '.join(self._cxxflags),
            'LDFLAGS': ' '.join(self._ldflags),
            'RCFLAGS': ' '.join(self._rcflags),
            'CPPFLAGS': ' '.join(self._cflags),
            'LIBS': '-lffi -lssl -lcrypto'
        })
        return env


    @property
    def _cc(self) -> Path:
        return self._clang_toolchain_dir / 'bin' / 'clang'

    @property
    def _cxx(self) -> Path:
        return self._clang_toolchain_dir / 'bin' / 'clang++'

    @property
    def _strip(self) -> Path:
        return self._clang_toolchain_dir / 'bin' / 'llvm-strip'
    
    
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
            '--with-system-ffi'
        ]
        cmd = [str(self._source_dir / 'configure')] + config_flags
        run_command(cmd, env=self._env, cwd=self._build_dir)
    

    def _copy_external_libs(self) -> None:
        self._logger.info("Copying external libraries...")
        # 定义源文件路径
        _external_libs = [self._deps_dir / 'ffi' / 'bin' / 'libffi-8.dll', self._clang_toolchain_dir / self.target_platform / 'bin' / 'libssp-0.dll']
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

    def _post_build(self) -> None:
        self._logger.info("Starting MinGW Python post-build...")
        super()._prepare_package()
        super()._package()
    
    
    def _clean_bin_dir(self) -> None:
        self._logger.info("Cleaning MinGW bin directory...")
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
