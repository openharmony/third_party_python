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
from typing import List
from python_builder import PythonBuilder, run_command

class LinuxPythonBuilder(PythonBuilder):
    def __init__(self, build_config) -> None:
        super().__init__(build_config)
        # Linux平台特有的补丁文件
        # Linux工具链路径（示例使用系统GCC）
        self._gcc_toolchain_dir = Path('/usr/bin').resolve()  # 系统GCC路径
        # 构建目录定义
        # 补丁检测文件（平台特定命名）
        self._patch_ignore_file = self._source_dir / 'linux_ignorefile.txt'

        # 验证Linux必要目录（示例检查源码目录和GCC）
        if not self._source_dir.is_dir():
            raise ValueError(f'No such source directory "{self._source_dir}"')
        if not (self._gcc_toolchain_dir / 'gcc').exists():
            raise ValueError(f'GCC not found in "{self._gcc_toolchain_dir}"')


    @property
    def _cflags(self) -> List[str]:
        # Linux通用编译标志（如优化选项、调试符号）
        return [
            '-D_FORTIFY_SOURCE=2 -O2',  # 优化等级
            '-fPIC',
            '-fstack-protector-strong',
            '-Wno-unused-command-line-argument',
            '-s'
        ]

    @property
    def _ldflags(self) -> List[str]:
        # Linux通用链接标志（如动态库路径）
        return [
            #f'-L{str(self._deps_dir / "ssl" / "lib64")}',
            '-Wl,-rpath,\\$$ORIGIN/../lib',
            '-Wl,--as-needed',
            '-Wl,-z,relro',
            '-Wl,-z,now'
        ]

    @property
    def _rcflags(self) -> List[str]:
        # Linux无资源编译器，此方法可留空
        return []

    def _deps_build(self) -> None:
        """依赖构建逻辑调整为Linux环境（使用系统GCC）"""
        self._logger.info("Starting Linux dependency build process...")
        env = os.environ.copy()
        env.update({
            'CC': "/usr/bin/gcc",  # 系统GCC
            'CXX': "/usr/bin/g++",
            'CFLAGS': "-O2 -fPIC -fstack-protector-strong -Wno-unused-command-line-argument",  # 编译标志
            'LDFLAGS': "-Wl,--as-needed -Wl,-z,relro,-z,now"  # 链接优化
        })
        ## TODO: 使用openssl+rpath实现依赖可追溯
        #self._deps_build_openssl(env)
        
    
    def _deps_build_libffi(self, env: dict) -> None:
        """构建libffi库"""
        self._logger.info("Building libffi...")
        libffi_inner_dir = self._extract_libffi()
        configure_cmd = [
            "./configure",
            f"--prefix={self._deps_dir / 'ffi'}",
            "--enable-shared",
            "--build=x86_64-linux-gnu",  # 构建平台
            "--host=x86_64-linux-gnu",   # 目标平台
            "--disable-docs"
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
        """配置参数调整为Linux目标"""
        self._logger.info("Starting Linux configuration...")
        config_flags = [
            f'--prefix={self._install_dir}',
            #f'--with-openssl={self._deps_dir / "ssl"}',
            #f'--with-openssl-rpath={self._deps_dir / "ssl" / "lib64"}',
            '--enable-shared',
            '--with-ensurepip=upgrade',
            '--disable-ipv6'
        ]
        cmd = [str(self._source_dir / 'configure')] + config_flags
        cmd.append('CFLAGS={}'.format(' '.join(self._cflags)))
        cmd.append('LDFLAGS={}'.format(' '.join(self._cflags + self._ldflags)))
        run_command(cmd, env=self._env, cwd=self._build_dir)


    def _post_build(self) -> None:
        self._logger.info("Starting Linux Python post-build...")
        super()._prepare_package()
        glibc_version = self._get_glibc_version()
        super()._package(glibc_version)
    


    def _copy_external_libs(self) -> None:
        self._logger.info("Linux Copy external_libs...")
        # 定义源文件路径
        #_external_libs = [self._deps_dir / 'ssl' / 'lib64' / 'libssl.so', self._deps_dir / 'ssl' / 'lib64' / 'libcrypto.so']
        # 定义目标目录
        #target_dir = self._install_dir / 'lib' / 'python3.11' / 'lib'
        # 创建目标目录（如果不存在）
        #target_dir.mkdir(parents=True, exist_ok=True)

        #try:
        #    for lib in _external_libs :
        #        # 调用提取的方法拷贝 libffi-8.dll
        #        self._copy_file_or_symlink_target(lib, target_dir)
        #except Exception as e:
        #    self._logger.error(f"Error copying external libraries: {e}")
    
    
    def _get_glibc_version(self):
        """
        通过执行 getconf 和 grep 命令获取 glibc 版本
        
        返回:
            str: 成功则返回版本号（如 "2.35"），失败则返回 None
        """
        try:
            # 构造命令管道：getconf | grep
            # 使用 shell=True 来支持管道操作
            result = subprocess.run(
                'getconf GNU_LIBC_VERSION | grep -oE \'[0-9]+\.[0-9]{2}\'',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 检查命令执行是否成功
            if result.returncode != 0:
                self._logger.error(f"Command failed with error: {result.stderr.strip()}")
                return None
            
            # 提取并清理版本号
            version = result.stdout.strip()
            if version:
                self._logger.info(f"Detected glibc version: {version}")
                return version
            else:
                self._logger.warning("No version information found in command output")
                return None
                
        except Exception as e:
            self._logger.error(f"Error executing command: {str(e)}")
            return None
