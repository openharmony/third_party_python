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
from typing import List, Mapping
from python_builder import PythonBuilder, run_command
import platform

class DarwinPythonBuilder(PythonBuilder):
    def __init__(self, build_config) -> None:
        super().__init__(build_config)
        self._patch_ignore_file = self._source_dir / 'darwin_ignorefile.txt'
        self.platform_arch = platform.machine()


    @property
    def _cc(self) -> Path:
        return Path('/usr/bin/clang')
 

    @property
    def _cxx(self) -> Path:
        return Path('/usr/bin/clang++')

    @property
    def _strip(self) -> Path:
        return Path('/usr/bin/strip')

    @property
    def _cxxflags(self) -> List[str]:
        return self._cflags.copy()
    
    @property
    def _cflags(self) -> List[str]:
        # macOS特有的编译标志（如最小系统版本、框架路径）
        return [
            '-mmacosx-version-min=10.14',
            '-DMACOSX_DEPLOYMENT_TARGET=10.14',
            f'-I{str(self._deps_dir / "ffi" / "include")}',
        ]

    @property
    def _ldflags(self) -> List[str]:
        # macOS特有的链接标志（如框架搜索路径、版本兼容）
        return [
            #f'-L{str(self._deps_dir / "ffi" / "lib")}',
            f'-L{str(self._deps_dir / "ssl" / "lib")}',
            '-Wl,-rpath,@loader_path/../lib',
            '-O2', '-fPIC', '-fstack-protector-strong', '-Wno-unused-command-line-argument'
        ]

    @property
    def _rcflags(self) -> List[str]:
        # macOS无windres，此方法可留空或根据需要调整（如资源文件处理）
        return []

    def _deps_build(self) -> None:
        """依赖构建逻辑调整为macOS环境（如使用clang编译）"""
        self._logger.info("Starting Darwin dependency build process...")

        env = os.environ.copy()
        env.update({
            'CC': "/usr/bin/clang",  # 使用Xcode的Clang
            'CXX': "/usr/bin/clang++",
            'CFLAGS': f"-arch {self.platform_arch} -mmacosx-version-min=10.15 -DHAVE_DYLD_SHARED_CACHE_CONTAINS_PATH=1",  # 架构和系统版本
            'LDFLAGS': f"-arch {self.platform_arch} -mmacosx-version-min=10.15"
        })
        self._deps_build_openssl(env)
        
    
    def _deps_build_libffi(self, env: dict) -> None:
        """构建libffi库"""
        self._logger.info("Building libffi...")
        libffi_inner_dir = self._extract_libffi()
        configure_cmd = [
            "./configure",
            f"--prefix={self._deps_dir / 'ffi'}",
        ]
        run_command(configure_cmd, env=env, cwd=libffi_inner_dir)
        run_command(['make', '-j16'], env=env, cwd=libffi_inner_dir)
        run_command(['make', 'install'], env=env, cwd=libffi_inner_dir)
    
    
    def _deps_build_openssl(self, env: dict) -> None:
        """构建openssl库"""
        self._logger.info("Building openssl...")
        openssl_dir = self.repo_root / 'third_party' / 'openssl'
        configure_cmd = [
            "./Configure",
            f"--prefix={self._deps_dir / 'ssl'}",
            "--shared",
        ]
        run_command(configure_cmd, env=env, cwd=openssl_dir)
        run_command(['make', '-j16'], env=env, cwd=openssl_dir)
        run_command(['make', 'install_sw'], env=env, cwd=openssl_dir)

    def _configure(self) -> None:
        """配置参数调整为macOS目标"""
        self._logger.info("Starting Darwin configuration...")
        config_flags = [
            f'--prefix={self._install_dir}',
            f'--with-openssl={self._deps_dir / "ssl"}',
            '--enable-shared',
            '--with-ensurepip=upgrade',
            '--enable-loadable-sqlite-extensions',
            '--disable-ipv6'
        ]
        cmd = [str(self._source_dir / 'configure')] + config_flags
        cmd.append('CFLAGS={}'.format(' '.join(self._cflags)))
        cmd.append('LDFLAGS={}'.format(' '.join(self._cflags + self._ldflags)))
        run_command(cmd, env=self._env, cwd=self._build_dir)

    def _post_build(self) -> None:
        self._logger.info("Starting Darwin Python post-build...")
        super()._prepare_package()
        self._dylib_rpath_setting()
        super()._package()
        
    
    def _copy_external_libs(self) -> None:
        self._logger.info("Darwin Copy external_libs...")
        # 定义源文件路径
        _external_libs = [self._deps_dir / 'ssl' / 'lib' / 'libssl.dylib', self._deps_dir / 'ssl' / 'lib' / 'libcrypto.dylib']
        # 定义目标目录
        target_dir = self._install_dir / 'lib' / 'python3.11' / 'lib'
        # 创建目标目录（如果不存在）
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            for lib in _external_libs :
                # 调用提取的方法拷贝 libffi-8.dll
                self._copy_file_or_symlink_target(lib, target_dir)
        except Exception as e:
            self._logger.exception(f"Error copying external libraries: {e}")
            
    
    def _dylib_rpath_setting(self) -> None:
        self._logger.info("Darwin dylib rpath setting...")
        prefix = str(self._deps_dir / 'ssl' / 'lib')
        python_exec = self._install_dir / 'bin' / 'python3.11'
        python_dylib = self._install_dir / 'lib' / 'libpython3.11.dylib'
        dylib_dir = self._install_dir / 'lib' / 'python3.11' / 'lib'
        _ssl_module_so = self._install_dir / 'lib' / 'python3.11' / 'lib-dynload' / '_ssl.cpython-311-darwin.so'
        
        try:
            run_command(["install_name_tool", "-id", f"@rpath/{python_exec.name}", f"{python_exec}"])
            run_command(["install_name_tool", "-change",  f"{python_dylib}", f"@rpath/{python_dylib.name}", f"{python_exec}"])
            run_command(["install_name_tool", "-id", f"@rpath/{python_dylib.name}", f"{python_dylib}"])
            
            for dylib in dylib_dir.iterdir() :
                try: 
                    file_name = dylib.name
                    prev_install_name = f'{prefix}/{file_name}'
                    run_command(["install_name_tool", "-id", f"@rpath/{file_name}", f"{dylib}"])
                    if 'ssl' in file_name:
                        run_command(["install_name_tool", "-change", f"{prefix}/libcrypto.3.dylib", "@rpath/libcrypto.3.dylib", f"{dylib}"])
                    run_command(["install_name_tool", "-change", f"{prev_install_name}", f"@rpath/{file_name}", f"{_ssl_module_so}"])
                    run_command(["codesign", "--remove-signature", f"{dylib}"])
                    run_command(["codesign", "-f", "-s", "-", f"{dylib}"])
                except Exception as e:
                    # 记录当前dylib处理失败的错误，但不退出循环
                    self._logger.exception(f"处理{dylib.name}时出错: {e}")
                    # 可以选择继续处理下一个或根据需要添加其他逻辑
                    continue
        except Exception as e:
            self._logger.exception(f"Error dylib rpath setting: {e}")
            raise