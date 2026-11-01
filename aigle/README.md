# Aigle's GPUI patch branches

This is a fork of https://github.com/zed-industries/zed. Aigle uses only
`crates/gpui`, `crates/gpui_linux`, and `crates/gpui_wgpu` from the versioned
`aigle/gpui-*` branches. The rest of Zed is unchanged.

Each branch has four commits on its exact upstream Zed revision:

1. This import tool and documentation (`aigle/packaging-tools-v1`).
2. The matching published `gpui-pre` packaging, including its small compatibility
   adaptations. Each crate gets an independent workspace so Cargo can use it
   without building or resolving the full Zed workspace.
3. Native surface ownership and hole-painting APIs for Aigle's Wayland HDR canvas.
4. Replacement blending for those holes in the WGPU renderer.

`aigle/baseline.json` records the published snapshot version, Zed revision, and
verified crate archive hashes. The `aigle/gpui-VERSION-base` tag marks the
packaging commit. Only commits after this tag are Aigle's HDR patches.

## Upgrade to a new published snapshot

Use a new branch for each version; do not rewrite a branch already pinned by
Aigle. Python 3.11+, Git, and network access to crates.io are required. The import
command verifies the registry's SHA-256 checksums and refuses to overwrite an
existing patched baseline.

From this fork's checkout, with a clean working tree:

```sh
# Add this once if the clone has only origin.
git remote add upstream https://github.com/zed-industries/zed.git

old=0.3.10
next=NEXT_VERSION
# Fetch the old patch range explicitly, including from a shallow/detached submodule.
git fetch origin \
  "refs/heads/aigle/gpui-${old}:refs/remotes/origin/aigle/gpui-$old" \
  "refs/tags/aigle/packaging-tools-v1:refs/tags/aigle/packaging-tools-v1" \
  "refs/tags/aigle/gpui-$old-base:refs/tags/aigle/gpui-$old-base"
if [ "$(git rev-parse --is-shallow-repository)" = true ]; then
  git fetch --deepen=4 origin "aigle/gpui-$old"
fi
revision=$(python3 aigle/import_snapshot.py --version "$next" --print-revision)
git fetch --depth=1 upstream "$revision"
git switch -c "aigle/gpui-$next" "$revision"
git cherry-pick aigle/packaging-tools-v1
python3 aigle/import_snapshot.py --version "$next"
git add crates/gpui crates/gpui_linux crates/gpui_wgpu aigle/baseline.json
git commit -m "Package gpui-pre $next for standalone Cargo builds"
git tag "aigle/gpui-$next-base"
git cherry-pick $(git rev-list --reverse "aigle/gpui-$old-base..origin/aigle/gpui-$old")
```

Resolve any conflicts in the two HDR commits, preserving their intent. In the
parent Aigle repository, update the `gpui-pre-*` version pins, the submodule
branch in `.gitmodules`, and its recorded gitlink. Then run workspace checks,
tests, and a GUI/HDR smoke test before publishing:

```sh
git push origin "aigle/gpui-$next" "refs/tags/aigle/gpui-$next-base"
```

Commit the new submodule revision in the parent repository only after that
revision is reachable from this fork. Fresh clones use
`git submodule update --init --recursive`; no local patch application is needed.
