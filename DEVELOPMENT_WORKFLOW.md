# tsurugi-dev development workflow

`tsurugi-dev` は `${TSURUGI_DEV_WORKSPACE}/tsurugidb` 配下の submodule をそのまま開発 checkout として使います。
`~/git/jogasaki` のような別 clone は作りません。

## 基本コマンド

### 1. build/install 環境を更地にする

```bash
tsurugi-dev clean
```

既知の CMake/Ninja/Gradle build output と、このツールの versioned install tree / `TSURUGI_HOME` symlink を削除します。
Git source tree、commit、branch は削除しません。

install tree を残したい場合だけ:

```bash
tsurugi-dev clean --keep-install
```

### 2. build して bin/lib を配置する

```bash
tsurugi-dev build
```

既存の `tsurugidb/install.sh` を利用して build/install し、設定済みの `TSURUGI_HOME` から `bin` / `lib` を利用できる状態にします。

### 3. submodule を直接使って開発 branch を作る

例: Jogasaki

```bash
tsurugi-dev dev start jogasaki udf-multiport
```

内部では概ね次を実行します。

```bash
cd "$TSURUGI_DEV_WORKSPACE/tsurugidb/jogasaki"
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c udf-multiport
```

現在の状態:

```bash
tsurugi-dev dev status jogasaki
```

commit は通常の Git 操作で行います。

```bash
cd "$TSURUGI_DEV_WORKSPACE/tsurugidb/jogasaki"
git add ...
git commit -m "..."
```

push:

```bash
tsurugi-dev dev push jogasaki
```

### 4. component 単位で CTest

```bash
tsurugi-dev test jogasaki
```

Jogasaki では既知の build directory `build-shirakami` を使用します。
別 build directory を使う場合:

```bash
tsurugi-dev test jogasaki --build-dir build-debug
```

テスト名を絞る場合:

```bash
tsurugi-dev test jogasaki --regex blob
```

### 5. GitHub merge 後に開発を終了する

```bash
tsurugi-dev dev finish jogasaki
```

通常 merge の場合は以下を行います。

```text
fetch origin
  -> feature branch が origin/master に取り込まれたことを確認
  -> master に switch
  -> origin/master まで fast-forward
  -> local feature branch を git branch -d で削除
```

GitHub の squash/rebase merge では feature branch の commit が `origin/master` の祖先にならないことがあります。
PR が merge 済みであることを別途確認した場合だけ:

```bash
tsurugi-dev dev finish jogasaki --force-delete
```

を使用します。

## tsurugidb 側の submodule gitlink を最新版へ更新する

component の開発終了後、親 `tsurugidb` が記録する submodule commit を更新する場合:

```bash
tsurugi-dev submodule update jogasaki -m "Update jogasaki"
```

これは概ね次を安全側に自動化します。

```bash
git submodule update --remote jogasaki
git add -- jogasaki
git commit -m "Update jogasaki"
git push
```

`git add .` ではなく対象 component の gitlink だけを stage します。

### submodule update のガード

`submodule update` は Jogasaki が以下のいずれかの場合だけ実行します。

- 通常の submodule 状態: detached HEAD が親 `tsurugidb` の pinned commit と一致
- `master` checkout 状態: clean で、`origin/master` より ahead していない
- `git submodule update --remote` 済み状態: detached HEAD が `origin/master` と一致

以下は拒否します。

- `udf-multiport` など開発 branch が checkout されている
- component に未commit変更がある
- `master` に未push/local-only commit がある
- 親 `tsurugidb` に対象 gitlink 以外の変更がある

開発 branch が残っている場合は、GitHub merge 後に先に:

```bash
tsurugi-dev dev finish jogasaki
```

を実行します。

親 commit は作るが push しない場合:

```bash
tsurugi-dev submodule update jogasaki \
  -m "Update jogasaki" \
  --no-push
```

## 通常の tsurugidb update と開発 branch

```bash
tsurugi-dev update
```

は pinned submodule を checkout するため、component が開発 branch の途中なら実行を拒否します。
開発が終わっている場合は:

```bash
tsurugi-dev dev finish jogasaki
tsurugi-dev update
```

の順にします。

## Jogasaki の一連の例

```bash
# 必要なら以前の build/install を削除
tsurugi-dev clean

# 最新 master から開発開始
tsurugi-dev dev start jogasaki udf-multiport

# ソース変更後、全体を build/install
tsurugi-dev build

# Jogasaki の CTest
tsurugi-dev test jogasaki

# commit
cd "$TSURUGI_DEV_WORKSPACE/tsurugidb/jogasaki"
git add ...
git commit -m "..."

# feature branch push
tsurugi-dev dev push jogasaki

# GitHub で PR merge

# local feature branch を削除して最新 master へ戻す
tsurugi-dev dev finish jogasaki

# merge 後の最新 master で再 build/test
tsurugi-dev build
tsurugi-dev test jogasaki

# 必要なら親 tsurugidb の gitlink も更新・commit・push
tsurugi-dev submodule update jogasaki -m "Update jogasaki"
```
