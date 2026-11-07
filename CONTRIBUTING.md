# Contributing

Bug reports, fixes, and protocol research are welcome.

## Report a problem

Open an [issue](https://github.com/Ammaar-Alam/g2-bridge/issues) with steps to reproduce the problem. Include your goggles model and firmware, operating system version, command, and a relevant log excerpt. Remove device serials and personal information from logs before sharing them.

## Submit a change

Fork the repository, create a branch, and open a pull request against `main`. Keep each pull request focused. Describe the problem, your change, and how you checked it.

Install the dependencies and run the offline tests from the repository root:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Add a regression test for a bug fix. For documentation changes, check links and command examples. Record any hardware checks separately, including the model, firmware, and settings used.

## Contribute protocol research

Start with the [protocol documentation](docs/PROTOCOL.md) and [reproduction guide](docs/research/REPRODUCE.md).

Include artifact hashes and the commands or packet bytes needed to reproduce your findings. Distinguish hardware observations from static analysis and hypotheses. Keep vendor binaries, decompiled vendor source, and personal recordings out of pull requests.

Contributions use the project's [GPL-3.0-only license](LICENSE).
