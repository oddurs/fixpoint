---
paths:
  - "build.py"
  - "main.asm"
  - "verify.py"
  - "demo/**"
---

# The image, its build, and its checks

- Comments and docstrings are lowercase prose in the project's voice and say why, as in
  `build.py:1`. Match it.
- `main.asm` must end exactly at the end of row 0, and its last 14 bytes must stay one
  period of the ether: `main.asm:81`. `build.py` places it by assembling twice
  (`build.py:49`).
- The stub's instructions carry their comments as `; ...` inside the unit strings in
  `stub_units` (`build.py:126`). Those comments become `stub.asm` and figure 1's panel (c).
- `demo/figures.py` traces the path from the file, not from `build.py`. It finds jumps by
  opcode (`EB`, `EA`) because ndisasm's text differs between nasm 2 and 3.
- Every claim on the project page is a check in `verify.py`. A new claim gets a new check.
