# Week 1 Setup | 第 1 周安装说明

## Install | 安装

```bash
cd ~/Desktop/PAHS
python3 -m venv .venv
source .venv/bin/activate
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .
```

If pip shows SSL certificate errors on macOS, run Python's certificate installer once:

```bash
/Applications/Python\ 3.*/Install\ Certificates.command
```

或在 Finder 里运行：`Applications` → `Python 3.x` → `Install Certificates.command`

## Initialize | 初始化

```bash
pah init-db
```

## Week 1 Demo | 演示

```bash
pah run "write a short post about AI"
pah pending
pah reply <run_id> "approved"
pah reply <run_id> "looks good"
pah status <run_id>
```

Expected:

1. `run` pauses for milestone review
2. first `reply approved` pauses for final feedback
3. second `reply` completes the run

## Notes | 说明

- Week 1 uses **mock LLM** only (no API keys required)
- Real DeepSeek integration starts after Week 1 flow is stable
