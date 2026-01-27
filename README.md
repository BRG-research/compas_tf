# compas_tf

Repository for the timber floor development.

<img width="2560" height="1440" alt="Screenshot from 2025-12-08 19-32-04" src="https://github.com/user-attachments/assets/09d2c68b-67c3-489d-9ef1-2f2fcbd17851" />

<img width="2560" height="1440" alt="image" src="https://github.com/user-attachments/assets/bad7b42c-1998-4b0e-ae74-81e7ee667522" />
<img width="2494" height="1568" alt="Screenshot from 2025-12-10 19-05-58" src="https://github.com/user-attachments/assets/496f0dd5-b06e-482c-b3a1-7ab65b1d3051" />

<img width="2494" height="1568" alt="Screenshot from 2025-12-10 19-06-33" src="https://github.com/user-attachments/assets/ab1e5a47-9f85-4785-ad50-eca10c7dbd6e" />


## Installation

### Option 1: Using uv (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager. Install it first:

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then set up the project:

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
uv venv .venv --python 3.12
uv pip install -e ".[dev]" compas_model compas_viewer
```

Activate the environment:

```bash
# Windows (Git Bash / MINGW64)
source .venv/Scripts/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat

# macOS/Linux
source .venv/bin/activate
```

Run an example:

```bash
python examples/test_quarter_floor.py
```

### Option 2: Using conda

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
conda create -n compas_tf python=3.12
conda activate compas_tf
pip install compas compas_viewer compas_model
pip install -e .
```

## Development

Run linting:

```bash
ruff check src/
```

Run tests:

```bash
pytest tests/
```
