# Getting started

## Requirements

- Python 3.12 or newer
- An S3-compatible object store. The reference target is Cloudflare R2 (free
  tier: 10 GB storage, free egress).

## Installation

Install directly from GitHub:

```
pip install "nimbus @ git+https://github.com/shrenikm/nimbus.git@main"
```

Or for local development:

```
git clone https://github.com/shrenikm/nimbus.git
cd nimbus
uv pip install -e ".[dev]"
```

`uv` is preferred for speed, but plain `pip install -e ".[dev]"` works too.

## Cloudflare R2 setup

You need three things from Cloudflare:

1. **Account ID** — Dashboard → R2 → right sidebar.
2. **Access Key ID** + **Secret Access Key** — Dashboard → R2 → *Manage R2
   API Tokens* → **Account API tokens** → Create. Permission **Object Read
   & Write**.

!!! warning "Two different things are called *token*"
    Cloudflare also has a separate "general API tokens" feature under your
    user profile. **That isn't what you want.** Only the *R2 API tokens*
    under R2 → Account API tokens hand out S3-compatible credentials.

!!! warning "The Secret is shown only once"
    On the token-creation confirmation page, scroll down to *"Use this
    token with the S3 API"*. Copy both Access Key ID and Secret Access Key
    before navigating away — Cloudflare never shows the secret again.

You also need to create the four buckets in the R2 dashboard up front:
`nimbus-raw-data`, `nimbus-datasets`, `nimbus-checkpoints`, `nimbus-test`.
Nimbus never creates or deletes buckets itself.

## Configuration

Nimbus reads configuration from environment variables. A `.env` file in
the current working directory is loaded automatically.

| Variable                 | Required | Purpose                                                |
|--------------------------|----------|--------------------------------------------------------|
| `R2_ENDPOINT_URL`        | one of   | Full S3-compatible endpoint URL.                       |
| `R2_ACCOUNT_ID`          | one of   | Alternative — nimbus builds the R2 endpoint URL.       |
| `R2_ACCESS_KEY_ID`       | yes      | Access key from the R2 API token.                      |
| `R2_SECRET_ACCESS_KEY`   | yes      | Matching secret.                                       |
| `NIMBUS_INTEGRATION_TESTS` | no     | Set to `1` to enable the opt-in integration suite.     |

The bucket names themselves (`nimbus-raw-data`, `nimbus-datasets`,
`nimbus-checkpoints`, `nimbus-test`) are fixed by the package — no env
variable overrides.

Example `.env`:

```
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret
```

See [`.env.example`](https://github.com/shrenikm/nimbus/blob/main/.env.example)
in the repo for the canonical template.

## First upload

With your `.env` in place:

```
nimbus upload test smoke-test hello_world.txt ./hello_world.txt
nimbus ls test smoke-test
nimbus download test smoke-test hello_world.txt /tmp/hello.txt
nimbus rm test smoke-test hello_world.txt
```

If that round-trips cleanly, you're set. From here:

- [CLI reference](cli.md) for the full command set.
- [API reference](api.md) for programmatic usage.
