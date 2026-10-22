#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Builds the hupf driver: b-inary/postflop-solver at a pinned commit + min_bet.patch -> target/release/hupf.
#
# Workarounds (both measured on rustc/cargo 1.97, 2026-10):
#   * RUSTFLAGS "-A dangerous_implicit_autorefs": upstream code from 2023 trips this lint, which newer
#     rustc reports as a hard error; allowing it keeps the upstream source untouched.
#   * HUPF_OFFLINE=1 adds --offline for a machine whose cargo registry is already populated but has no
#     route to crates.io; versions stay pinned by Cargo.lock either way (--locked).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM="https://github.com/b-inary/postflop-solver.git"
COMMIT="9d1509fe5077d019825f833eed04b16d342dfda1"
VENDOR="$HERE/vendor/postflop-solver"

if [ ! -d "$VENDOR/.git" ]; then
  mkdir -p "$VENDOR"
  git -C "$VENDOR" init --quiet
  git -C "$VENDOR" remote add origin "$UPSTREAM"
fi
if ! git -C "$VENDOR" cat-file -e "$COMMIT^{commit}" 2>/dev/null; then
  git -C "$VENDOR" fetch --quiet --depth 1 origin "$COMMIT"
fi
# --force: vendor/ is a build directory; a previously applied patch is discarded and re-applied.
git -C "$VENDOR" checkout --quiet --force --detach "$COMMIT"
git -C "$VENDOR" apply "$HERE/min_bet.patch"

export RUSTFLAGS="${RUSTFLAGS:-} -A dangerous_implicit_autorefs"
offline=()
if [ "${HUPF_OFFLINE:-0}" = "1" ]; then
  offline=(--offline)
fi
cargo build --release --locked "${offline[@]}" --manifest-path "$HERE/Cargo.toml"
echo "hupf: $HERE/target/release/hupf"
