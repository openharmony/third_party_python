#!/bin/bash

# build.sh - 检测系统类型并执行相应的构建命令
compileType="$1"
# 设置错误时退出
set -e

APPHOME="$(pwd)"

echo "=== 系统类型检测 ==="
function code_pull_prebuilts_download() {
#  流水线有拉取更新代码脚本直接安装环境依赖
    echo "下载预编译工具"
    ./build/prebuilts_download.sh
}

function ubuntu_build() {
    code_pull_prebuilts_download
    apt-get install -y libgdbm-dev lzma liblzma-dev bzip2 libbz2-dev xz-utils sqlite3 libreadline-dev libsqlite3-dev libsqlite-dev libdb-dev tk-dev uuid-dev

    echo "安装 autoconf-archive"
    apt install -y autoconf-archive
    echo "安装 autoconf automake libtool"
    apt install -y autoconf automake libtool

    echo "开始编译"
    if [ "$compileType" == "mingw" ]; then
    echo "mingw编译 安装mingw-w64"
    apt install -y mingw-w64
    cd third_party
    echo "进入third_part预制 libffi"
    git clone https://gitcode.com/openharmony/third_party_libffi.git libffi
        $APPHOME/prebuilts/python/linux-x86/current/bin/python3 $APPHOME/third_party/python/.cid/build.py  --repo-root  $APPHOME  --out-path $APPHOME/out  --lldb-py-version  3.12.10 --target-os  mingw  --target-arch x86
    else
        CPU=$(case "$(uname -m)" in *aarch64*|*arm64*) echo arm64 ;; *) echo x86 ;; esac)
        echo "CPU架构信息: $(uname -m)"
        $APPHOME/prebuilts/python/linux-${CPU}/current/bin/python3 \
            $APPHOME/third_party/python/.cid/build.py \
            --repo-root  $APPHOME  \
            --out-path $APPHOME/out  \
            --lldb-py-version  3.12.10 \
            --target-os  linux  \
            --target-arch $CPU    fi
    # remove_redundancy_for_out
}

function remove_redundancy_for_out() {
    echo "删除out文件夹多余文件"
    cd $APPHOME/out
    find . -depth -mindepth 1 -name "*.tar.gz" -prune -o -exec rm -rf {} +
}

function macos_build() {
    code_pull_prebuilts_download
    echo "正在执行 macOS 构建命令..."
    cd $APPHOME/prebuilts/python
    echo "python 路径： $(ls)"
    $APPHOME/prebuilts/python/darwin-$1/current/bin/python3 $APPHOME/third_party/python/.cid/build.py  --repo-root  $APPHOME  --out-path $APPHOME/out  --lldb-py-version  3.12.10 --target-os  darwin  --target-arch $1
    echo "macOS 构建完成!"
    # remove_redundancy_for_out
}

function macos_info() {
    # macOS 系统
    echo "检测到系统: macOS"
    echo "型号信息: $(uname -m)"
    if [[ $(uname -m) == *"arm64"* ]]; then
        echo "检测到arm64"
        macos_build "$(uname -m)"
    elif [[ $(uname -m) == *"x86"* ]]; then
        echo "检测到x86"
        macos_build "x86"
    else
        echo "其他型号"
    fi
}

function main() {
    # 检测当前系统类型
    if [ -f "/etc/os-release" ]; then
        # Linux 系统
        source /etc/os-release
        if [ "$ID" == "ubuntu" ]; then
            echo "检测到系统: Ubuntu"
            echo "版本信息: $VERSION"
            echo "CPU架构信息: $(uname -m)"
            if [[ "$VERSION" == "22"*  || "$VERSION" == "18"* ]]; then
                ubuntu_build "$VERSION"
            else
                echo "不支持的 Ubuntu 版本: $VERSION"
                exit 1
            fi
            # Ubuntu 特定的构建命令
            echo "正在执行 Ubuntu 构建命令..."
            # 这里添加 Ubuntu 特有的构建步骤
            echo "Ubuntu 构建完成!"
        else
            echo "检测到 Linux 系统，但不是 Ubuntu: $ID"
            echo "版本信息: $VERSION"
            # 其他 Linux 发行版的构建命令
            echo "正在执行通用 Linux 构建命令..."
            # 这里添加通用 Linux 构建步骤
            echo "Linux 构建完成!"
        fi
    elif [ "$(uname -s)" == "Darwin" ]; then
      macos_info
    else
        echo "错误: 无法识别的系统类型"
        echo "当前系统: $(uname -s)"
        exit 1
    fi
}
main