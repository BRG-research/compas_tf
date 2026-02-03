# compas_tf

Repository for the timber floor development.

<img width="2560" height="1440" alt="Screenshot from 2025-12-08 19-32-04" src="https://github.com/user-attachments/assets/09d2c68b-67c3-489d-9ef1-2f2fcbd17851" />

<img width="2560" height="1440" alt="image" src="https://github.com/user-attachments/assets/bad7b42c-1998-4b0e-ae74-81e7ee667522" />
<img width="2494" height="1568" alt="Screenshot from 2025-12-10 19-05-58" src="https://github.com/user-attachments/assets/496f0dd5-b06e-482c-b3a1-7ab65b1d3051" />

<img width="2494" height="1568" alt="Screenshot from 2025-12-10 19-06-33" src="https://github.com/user-attachments/assets/ab1e5a47-9f85-4785-ad50-eca10c7dbd6e" />


## Quick Setup (Git Bash)

```bash
cd /c/brg/compas_tf
source .venv/Scripts/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

## Run

```bash
python examples/model.py
```

## Fresh Install

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
uv venv .venv --python 3.12
source .venv/Scripts/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e ".[dev]" compas_model compas_viewer
```
