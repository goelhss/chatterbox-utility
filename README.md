# Local Chatterbox utility

A local web interface for recording a consenting speaker's reference, reviewing a sample, and converting text to MP3 with [Resemble AI Chatterbox](https://github.com/resemble-ai/chatterbox). The CLI retains segment WAVs so a long conversion can resume after an interruption. Output filenames follow input filenames; `-o` selects an export path.

Install at `~/utils/chatterbox` on either Ubuntu or macOS. The setup scripts download Chatterbox at a pinned upstream commit, install Python 3.11 and dependencies into `.venv`, and download the Turbo model into `models/`. They normally need no sudo if `curl` and `git` are present. First setup requires internet access and several gigabytes of free space. The model runs locally afterward.

## Ubuntu

```sh
mkdir -p ~/utils
cd ~/utils
git clone https://github.com/goelhss/chatterbox-utility.git chatterbox
cd chatterbox
scripts/ubuntu/setup.sh
scripts/ubuntu/start.sh
```

Open <http://127.0.0.1:7860/> on Ubuntu. For access from a phone on trusted local Wi-Fi, start with `scripts/ubuntu/start.sh --lan` and use the Ubuntu machine's LAN address. The login is generated at `tools/web-login.json`; keep it private. `--lan` serves local HTTP without encryption. Leave the terminal open while using the GUI.

For an NVIDIA GPU with a compatible driver, select a [PyTorch 2.6.0 CUDA wheel index](https://docs.pytorch.org/get-started/previous-versions/) before setup, for example:

```sh
CHATTERBOX_TORCH_INDEX=https://download.pytorch.org/whl/cu126 scripts/ubuntu/setup.sh
```

The setup defaults to CPU PyTorch. For a different CUDA or ROCm version, use the corresponding official 2.6.0 wheel index. Check availability after installation:

```sh
.venv/bin/python -c 'import torch; print(torch.__version__, torch.cuda.is_available())'
```

A GPU driver is an operating-system prerequisite; installing one may require sudo. If `git` or `curl` is missing, install those with your package manager (on Ubuntu, `sudo apt install git curl`). The Python and Chatterbox installation itself runs in your user account. No system `ffmpeg` installation is needed: `imageio-ffmpeg` provides the converter used by this utility.

## macOS

For a fresh installation in an empty `~/utils/chatterbox` location:

```sh
mkdir -p ~/utils
cd ~/utils
git clone https://github.com/goelhss/chatterbox-utility.git chatterbox
cd chatterbox
scripts/mac/setup.sh
scripts/mac/start.sh
```

If you already have the older standalone utility at this path, keep its data in place and install this repository in a separate temporary directory first; copy only the public scripts and tools into the existing utility. Then run `scripts/mac/setup.sh` there.

The Mac launchers use `caffeinate` to prevent idle sleep while running. Apple MPS is selected when available.

## Voice and conversion workflow

In the GUI, use **Add a new voice** to record or upload a 20–30 second reference from a consenting speaker. Generate a sample, listen and check it, then approve the voice for chapters. Saved references and approvals are reused after reopening the GUI.

Run CLI conversions from the install directory:

```sh
scripts/ubuntu/convert.sh --voice VoiceName --text '/path/Chapter 1.txt' --whole-chapter -o 'Chapter 1.mp3'
# On Mac, use scripts/mac/convert.sh with the same options.
```

Omit `-o` to keep the MP3 in the local `output/` cache. `Chapter 1.txt` becomes `Chapter 1.mp3`; `--chapter NAME` overrides the name. `-o` will not overwrite an existing file. Conversion progress is printed in the terminal. The GUI can also load a whole book or chapter files and resume saved chapter progress.

### Convert separate chapters concurrently

Put each chapter in its own `.txt` file, then run:

```sh
scripts/ubuntu/convert-chapters.sh --voice VoiceName --input-dir '/path/to/chapters' --jobs 2
# On Mac, use scripts/mac/convert-chapters.sh with the same options.
```

Each chapter produces a separate MP3 in `~/utils/chatterbox/output/chapters/`; use `--output-dir '/another/folder'` to change that. `--dry-run` previews filenames without converting. Each chapter has its own progress log under `logs/`. Existing MP3s are skipped without being overwritten; check them before relying on them. Each concurrent job loads a copy of the model, so start with two jobs and increase only if the machine has enough RAM. This command takes separate chapter files; splitting a partially converted whole-book file changes its cache identity. To resume a cancelled whole-file conversion, rerun the same original command with the same voice and unchanged text.

## Moving an existing installation

For the smallest move, copy only `recordings/` into `~/utils/chatterbox/`. This keeps your saved voice references and approvals. Then run the setup script on the new machine; it downloads the model and builds a new Python environment.

The other data is optional: `models/` saves a model download, `books/` keeps GUI book queues and progress, and `output/` keeps earlier MP3s and cached segments. Copy `books/` together with its referenced `output/` files if you want completed chapters to remain marked ready. Copy `tools/web-login.json` only if you want the same login; otherwise a new one is generated. Do not copy `.venv/` or Mac binaries.

Personal recordings, approvals, book text/progress, models, logs, credentials, and audio are excluded by `.gitignore`. Review `git status --short` before publishing changes. This repository contains utility code and setup scripts; upstream Chatterbox is downloaded separately under `tools/chatterbox/` and retains its own license.
