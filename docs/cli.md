# CLI reference

The `nimbus` console script is installed by `pip install nimbus`. Help is
available everywhere via `-h` or `--help`; running `nimbus` with no
arguments shows the top-level help.

```
nimbus -h                    # top-level help
nimbus <command> -h          # per-command help
```

`<bucket-type>` in all of the below is one of:
`raw-data | datasets | checkpoints | test`.

## Single-object commands

### `nimbus upload`

```
nimbus upload <bucket-type> <project> <key> <local-path> [--no-progress]
```

Upload a local file to `<bucket-type>/<project>/<key>`. Shows a tqdm
progress bar by default; suppress with `--no-progress`.

```
nimbus upload checkpoints my-project run-abc/best.pth ./best.pth
```

### `nimbus download`

```
nimbus download <bucket-type> <project> <key> <local-path> [--no-progress]
```

Download an object to a local file. Creates parent directories as needed.

```
nimbus download checkpoints my-project run-abc/best.pth ./best.pth
```

### `nimbus ls`

```
nimbus ls <bucket-type> <project> [<key-prefix>]
```

List all object keys under `<project>` (optionally filtered by
`<key-prefix>`). Keys are printed with the project prefix stripped.

```
nimbus ls datasets shared
nimbus ls checkpoints my-project run-abc/
```

### `nimbus exists`

```
nimbus exists <bucket-type> <project> <key>
```

Check whether an object is present. Exits **0** if yes, **1** if no.

```
nimbus exists checkpoints my-project run-abc/best.pth && echo "found"
```

### `nimbus rm`

```
nimbus rm <bucket-type> <project> <key>
```

Delete a single object. Succeeds silently if already gone.

### `nimbus presign`

```
nimbus presign <bucket-type> <project> <key> [--expires <seconds>]
```

Generate a presigned GET URL for sharing. Default lifetime 3600 seconds.

```
nimbus presign datasets shared my-dataset-v1/sample.parquet --expires 7200
```

## Directory commands

These do concurrent per-file transfers (default 8 workers); within a
single file, multipart chunks are also parallel via boto3.

### `nimbus upload-dir`

```
nimbus upload-dir <bucket-type> <project> <local-dir> [--prefix <key-prefix>] [--no-progress]
```

Recursively upload every file under `<local-dir>` to
`<bucket-type>/<project>/<prefix>/...`.

**The local directory name itself is not part of the key** — only its
contents are uploaded under the prefix. Same semantics as
`rsync local_dir/ dest/` or `aws s3 sync`. Given local tree

```
a/
├── c.txt
└── b/
    └── d.txt
```

then `nimbus upload-dir test P a --prefix z/` produces:

```
P/z/c.txt
P/z/b/d.txt
```

(Not `P/z/a/c.txt` — `a` is stripped.) An empty `--prefix` (the default)
uploads directly under the project namespace.

```
nimbus upload-dir datasets shared ./my-dataset --prefix v1/
```

### `nimbus download-dir`

```
nimbus download-dir <bucket-type> <project> <local-dir> [--prefix <key-prefix>] [--no-progress]
```

Exact mirror of `upload-dir`. Recursively downloads every object under
`<bucket-type>/<project>/<prefix>` into `<local-dir>`, preserving the
key structure beneath the prefix. Creates `<local-dir>` if missing.

Given remote keys

```
P/z/c.txt
P/z/b/d.txt
```

`nimbus download-dir test P ./out --prefix z/` writes:

```
out/
├── c.txt
└── b/
    └── d.txt
```

An empty `--prefix` (the default) downloads the whole project, preserving
the full key structure (so `out/z/c.txt`, `out/z/b/d.txt` above).

```
nimbus download-dir datasets shared ./local-copy --prefix v1/
```

## Test-bucket maintenance

### `nimbus purge-test-bucket`

```
nimbus purge-test-bucket [--yes | -y]
```

Delete every object in the `test` bucket. Hardcoded — cannot be used
against any other category. Prompts for confirmation; `--yes` skips the
prompt.

```
nimbus purge-test-bucket --yes
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success. |
| 1 | A `NimbusError` was raised (config, storage, validation). `nimbus exists` also exits 1 when the object is missing. |
| 2 | Either no command given (typer convention), or `NimbusObjectNotFoundError` for a download/exists. |
