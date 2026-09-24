# Environment probes (owner provides)

Claude pins the lab's Python version and checks machine details from these two files. Create each once, and again whenever Colab or the Oracle VM changes.

## colab_probe.txt
1. Open a new notebook at colab.research.google.com. A CPU runtime is enough.
2. Paste this into one cell and run it:
```text
!python --version
!python -c "import sys, platform; print(sys.version); print(platform.platform())"
!pip --version
!nvidia-smi || echo "no GPU on this runtime"
!cat /etc/os-release | head -4
!uname -m
!df -h /content | tail -1
!free -g | head -2
```
3. Copy the whole output. On GitHub, in this folder on `main`, choose **Add file → Create new file**, name it `colab_probe.txt`, paste, and commit.

## oracle_probe.txt
On the Oracle VM, run the following and save the output the same way as `oracle_probe.txt`:
```text
uname -m; cat /etc/os-release | head -4; python3 --version; nproc; free -g | head -2; df -h / | tail -1; lscpu | grep "Model name"
```
