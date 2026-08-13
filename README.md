# tsurugi-dev

`project-tsurugi/tsurugidb` の公式 `install.sh` を利用する開発用 CLI です。

Tsurugi 各コンポーネントのビルド順序や通常の CMake オプションは再実装せず、公式 installer に任せます。このツールは、開発環境で頻繁に必要になる **環境設定、フルビルド、差分ビルド、clean、update、外部 checkout 差し替え、検証**を整理します。

Python の外部 runtime dependency はありません。Python 3.10 以上を使用します。

______________________________________________________________________

## 1. tsurugi-dev 自体のインストール

このリポジトリで次を実行します。

```bash
python3 -m pip install -e .
```

editable install なので、`src/tsurugi_dev/` を変更すると再インストールせず反映されます。

確認:

```bash
tsurugi-dev --version
tsurugi-dev --help
```

`pip` を使わず実行したい場合も、source tree で次の形式が使えます。

```bash
PYTHONPATH=src python3 -m tsurugi_dev --help
```

______________________________________________________________________

## 2. 環境設定

通常は `~/.bashrc` などに次を設定します。

```bash
export TSURUGI_HOME="${HOME}/git/.local-relwithdebinfo"
export TSURUGI_CONF="${HOME}/tsurugi.ini"

export PATH="${TSURUGI_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${TSURUGI_HOME}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
```

反映:

```bash
source ~/.bashrc
```

`tsurugi-dev` は `--home` がない場合、次の順番で Tsurugi home を決定します。

1. `$TSURUGI_HOME`
1. `~/git/tsurugi`

そのため、通常は `--home` を毎回指定する必要はありません。

`TSURUGI_CONF` が設定されていればそれを使用し、未設定なら `${TSURUGI_HOME}/var/etc/tsurugi.ini` を使用します。

現在の設定に対応する export を表示するには:

```bash
tsurugi-dev env
```

例:

```text
export TSURUGI_HOME=/home/user/git/.local-relwithdebinfo
export TSURUGI_CONF=/home/user/tsurugi.ini
export PATH="${TSURUGI_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${TSURUGI_HOME}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
```

### UDF 用のパス

`TSURUGI_PROTO` は Tsurugi 本体の標準環境変数としては扱いません。UDF 開発用の基準ディレクトリが必要なら、例えば次のように分離します。

```bash
export TSURUGI_UDF_HOME="${HOME}/git/tsurugi-udf"
```

proto は `${TSURUGI_UDF_HOME}/proto` として参照します。

______________________________________________________________________

## 3. 初回準備

Tsurugi source tree を clone 済みとして、まず source と submodule を揃えます。

```bash
cd ~/git/tsurugidb
tsurugi-dev update
```

ビルド前の確認:

```bash
tsurugi-dev doctor
```

依存 OS package が未導入なら、Tsurugi 側の公式手順で導入してください。

______________________________________________________________________

## 4. フルビルド

初回、ビルド設定変更後、build tree の不整合が疑われる場合は:

```bash
tsurugi-dev full-build
```

`full-build` は公式 installer に `TG_CLEAN_BUILD=clean` を設定して実行します。

デフォルト build type:

```text
RelWithDebInfo
```

Debug:

```bash
tsurugi-dev full-build --build-type Debug
```

### 並列数

デフォルトは:

```text
--parallel auto
```

です。

`auto` は次の情報から並列数を決めます。

- `sched_getaffinity()` でこのプロセスが使用可能な CPU 数
- Linux `/proc/meminfo` の `MemAvailable`

メモリ側は安全側の初期値として、2 GiB を OS 等のために残し、C/C++ build 1 job あたり 2 GiB と見積もります。

実行時に決定値を表示します。

```text
parallel: 12 (auto: cpu=16, memory=27.5 GiB, memory-limit=12)
```

明示指定もできます。

```bash
tsurugi-dev full-build --parallel 8
```

通常は `--parallel` を指定せず auto のまま使うことを推奨します。

______________________________________________________________________

## 5. 差分ビルド

通常のソース修正後はこちらを使います。

```bash
tsurugi-dev build
```

同じ意味の alias:

```bash
tsurugi-dev diff-build
```

公式 installer に:

```text
TG_CLEAN_BUILD=keep
```

を設定するため、既存 CMake/Ninja build tree を残したまま再構成・再ビルドします。

例:

```bash
cd ~/git/tsurugidb
vi jogasaki/...
tsurugi-dev build
```

特定 checkout を使う場合:

```bash
tsurugi-dev build \
  --component-dir jogasaki=~/git/jogasaki
```

複数指定も可能です。

```bash
tsurugi-dev build \
  --component-dir jogasaki=~/git/jogasaki \
  --component-dir data-relay-grpc=~/git/data-relay-grpc
```

現在の公式 installer が持つ `TG_*_DIR` を利用するため、ラッパー側で各コンポーネントのビルド手順を複製しません。

______________________________________________________________________

## 6. clean

既知の build output を削除します。

```bash
tsurugi-dev clean
```

削除対象だけ確認:

```bash
tsurugi-dev clean --dry-run
```

`tsubakuro` / `tanzawa` / `harinoki` の Gradle clean を行わない場合:

```bash
tsurugi-dev clean --skip-gradle
```

このツールが作成した versioned install tree も削除する場合:

```bash
tsurugi-dev clean --install
```

`clean --install` は `TSURUGI_HOME` に対応する install tree まで対象になるため、通常の `clean` より影響範囲が大きい操作です。

______________________________________________________________________

## 7. update

親 `tsurugidb` と pinned submodule を更新します。

```bash
tsurugi-dev update
```

内部では:

```bash
git pull --ff-only
git submodule sync --recursive
git submodule update --init --recursive
```

を実行します。

親 repository を pull せず、現在の commit に対応する submodule だけ揃える場合:

```bash
tsurugi-dev update --no-pull
```

submodule update の並列数:

```bash
tsurugi-dev update --jobs 8
```

実行コマンドだけ確認:

```bash
tsurugi-dev update --dry-run
```

______________________________________________________________________

## 8. doctor

ビルド前の簡易診断です。

```bash
tsurugi-dev doctor
```

主に次を表示・確認します。

- `TSURUGI_HOME`
- `TSURUGI_CONF`
- auto parallel の決定値
- `git`, `cmake`, `ninja`, `make`, `tar`, `curl`, `java`
- 必要な submodule checkout
- Git branch / HEAD

standalone checkout を診断対象に含める場合:

```bash
tsurugi-dev doctor \
  --component-dir data-relay-grpc=~/git/data-relay-grpc
```

______________________________________________________________________

## 9. verify

インストール結果を確認します。

```bash
tsurugi-dev verify
```

主な確認対象:

```text
bin/tsurugidb
bin/tgctl
bin/tgsql
bin/tgdump
lib/libtsubakuro.so*
var/etc/tsurugi.ini
var/data
var/blob/sessions
var/plugins
TSURUGI_CONF
```

`ldd` が使用できる場合、`${TSURUGI_HOME}/bin/tsurugidb` の unresolved shared library (`not found`) も確認します。

______________________________________________________________________

## 10. TSURUGI_HOME と install directory

公式 `install.sh` は `--prefix` の下に:

```text
tsurugi-<version>
```

を作ります。

このツールは開発用 version 名を固定し、例えば RelWithDebInfo では実体を:

```text
~/git/tsurugi-dev-relwithdebinfo
```

へ作ります。

`TSURUGI_HOME` が:

```text
~/git/.local-relwithdebinfo
```

なら、成功後に:

```text
~/git/.local-relwithdebinfo -> ~/git/tsurugi-dev-relwithdebinfo
```

という symlink を作ります。

旧スクリプトにより `${TSURUGI_HOME}` が実 directory の場合は、最初に退避するのが安全です。

```bash
mv "${TSURUGI_HOME}" "${TSURUGI_HOME}.old"
tsurugi-dev full-build
```

バックアップ済みで意図的に置換する場合のみ:

```bash
tsurugi-dev full-build --replace-home
```

`--replace-home` は既存の通常 file/directory を削除する破壊的オプションです。

______________________________________________________________________

## 11. 引数一覧

### グローバル

#### `--repo PATH`

`tsurugidb` source tree。デフォルトは current directory。

```bash
tsurugi-dev --repo ~/git/tsurugidb build
```

`--repo` は subcommand より前に指定します。

#### `--version`

`tsurugi-dev` 自体の version を表示します。

______________________________________________________________________

### `full-build` / `build`

#### `--home PATH`

runtime の Tsurugi home。

優先順位:

1. `--home`
1. `$TSURUGI_HOME`
1. `~/git/tsurugi`

#### `--prefix PATH`

公式 installer の install parent directory。省略時は `TSURUGI_HOME` の親 directory。

#### `--build-type TYPE`

指定可能値:

```text
Debug
Release
RelWithDebInfo
```

デフォルトは `RelWithDebInfo`。

#### `--name NAME`

公式 installer に渡す開発用 version 名。省略時は `dev-<build-type>`。

通常は指定不要です。

#### `--parallel auto|N`

build の並列数。デフォルトは `auto`。

```bash
tsurugi-dev build --parallel auto
tsurugi-dev build --parallel 8
```

`auto` は CPU affinity と `MemAvailable` から数値に解決し、公式 installer へ必ず `--parallel=<数値>` として渡します。

#### `--component-dir COMPONENT=PATH`

特定 component を submodule ではなく外部 checkout へ差し替えます。繰り返し指定可能。

指定可能 component:

```text
data-relay-grpc
harinoki
jogasaki
limestone
mizugaki
sharksfin
shirakami
takatori
tanzawa
tateyama
tateyama-bootstrap
tsubakuro
yakushima
yugawara
```

#### `--ccache`

C/C++ compiler launcher に `ccache` を使用します。PATH にない場合はエラー。

#### `--tracy`

共通 CMake option に `-DTRACY_ENABLE=ON` を追加。

#### `--altimeter`

共通 CMake option に `-DENABLE_ALTIMETER=ON` を追加。

#### `--no-jemalloc`

Tateyama Bootstrap の jemalloc を無効化。

#### `--force-mpdecimal`

公式 installer に bundled mpdecimal のインストールを強制。

#### `--cmake-option=-DNAME=VALUE`

`TG_COMMON_CMAKE_BUILD_OPTIONS` に追加。繰り返し指定可能。

```bash
tsurugi-dev build \
  --cmake-option=-DFOO=ON \
  --cmake-option=-DBAR=VALUE
```

#### `--shirakami-option=-DNAME=VALUE`

`TG_SHIRAKAMI_OPTIONS` に追加。繰り返し指定可能。

#### `--skip TARGET`

公式 installer の group をスキップ。指定可能値:

```text
server
nativelib
tanzawa
harinoki
grpc
```

`grpc` は通常の Data Relay gRPC と Tateyama の gRPC support を公式 installer の仕組みで無効化します。

#### `--replace-config SECTION.KEY=VALUE`

公式 `--replaceconfig` に転送。繰り返し指定可能。

#### `--replace-home`

既存の非 symlink `TSURUGI_HOME` を、ビルド成功後に新 install tree への symlink へ置換。破壊的。

#### `--verbose`

公式 installer の verbose output を有効化。

#### `--dry-run`

コマンドを表示するだけで実行しない。

______________________________________________________________________

### `clean`

`--home`, `--prefix`, `--build-type`, `--name`, `--component-dir` に加え:

#### `--skip-gradle`

Gradle clean を行わない。

#### `--install`

versioned install tree と対応 symlink も削除。

#### `--dry-run`

削除対象のみ表示。

______________________________________________________________________

### `update`

#### `--no-pull`

親 `tsurugidb` の `git pull --ff-only` を実行しない。

#### `--jobs N`

`git submodule update` の並列数。

#### `--dry-run`

Git command を表示するだけで実行しない。

______________________________________________________________________

### `doctor`

#### `--home PATH`

診断に使う Tsurugi home を上書き。

#### `--component-dir COMPONENT=PATH`

外部 checkout を source tree 検査対象に使用。

______________________________________________________________________

### `verify`

#### `--home PATH`

確認対象の Tsurugi home を上書き。

______________________________________________________________________

### `env`

#### `--home PATH`

生成する `TSURUGI_HOME` を上書き。

#### `--conf PATH`

生成する `TSURUGI_CONF` を上書き。

______________________________________________________________________

## 12. ライブラリとして再利用する

`tsurugi-dev` は CLI だけでなく、別の開発・環境構築ツールから再利用できる共通処理を `tsurugi_dev.common` に分離しています。

```text
src/tsurugi_dev/
├── common/
│   ├── process.py   # subprocess 実行、dry-run、stdout capture
│   ├── git.py       # pull / submodule sync / update
│   └── system.py    # CPU・メモリ取得、parallel auto 判定
├── config.py        # Tsurugi 固有設定
├── upstream.py      # Tsurugi 公式 install.sh との連携
└── cli.py           # tsurugi-dev CLI
```

`common` 配下には Tsurugi 固有、gRPC 固有、GRDMA 固有のビルド手順を置きません。これにより、将来別の環境構築ツールを作る場合も同じ処理を import して利用できます。

### parallel auto の再利用

```python
from tsurugi_dev.common.system import auto_parallel

decision = auto_parallel()
print(decision.jobs)
print(decision.reason)
```

メモリ見積りを変える場合:

```python
decision = auto_parallel(
    memory_per_job_gib=3.0,
    memory_reserve_gib=4.0,
)
```

### command 実行の再利用

```python
from pathlib import Path
from tsurugi_dev.common.process import run

run(
    ["cmake", "--build", "build", "--parallel", "8"],
    cwd=Path("/path/to/source"),
)
```

`dry_run=True` を渡すと実行せず、実行予定 command だけ表示します。

```python
run(["cmake", "--build", "build"], dry_run=True)
```

### Git 更新処理の再利用

```python
from pathlib import Path
from tsurugi_dev.common.git import update_repository

update_repository(
    Path("/path/to/repository"),
    pull=True,
    jobs=8,
)
```

この関数は次をまとめて実行します。

```text
git pull --ff-only
git submodule sync --recursive
git submodule update --init --recursive
```

必要なら個別関数も使用できます。

```python
from tsurugi_dev.common.git import (
    pull_ff_only,
    sync_submodules,
    update_submodules,
)
```

この方針により、別の環境構築コード側でプロセス実行、Git操作、マシン状況に応じた並列数決定を再実装する必要がありません。専用の環境構築ロジック自体は、その別ツール側に置きます。

______________________________________________________________________

## 13. テスト

外部 test framework は不要です。

```bash
python3 -m unittest discover -s tests -v
```

主に以下を確認します。

- `TSURUGI_HOME` / `TSURUGI_CONF` の優先順位
- parallel auto 判定
- `--parallel auto|N` の CLI parsing
