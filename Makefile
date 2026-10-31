PYTHON ?= python3

all: fixpoint.bmp docs/anatomy.svg

# build.py also regenerates stub.asm (the stub is chosen by search)
fixpoint.bmp: main.asm build.py
	$(PYTHON) build.py

verify: fixpoint.bmp
	$(PYTHON) verify.py

run: fixpoint.bmp
	qemu-system-i386 -drive format=raw,file=fixpoint.bmp

docs/anatomy.svg: fixpoint.bmp demo/figures.py
	$(PYTHON) demo/figures.py

demo: fixpoint.bmp docs/anatomy.svg
	$(PYTHON) demo/record.py

site: fixpoint.bmp
	cd site && npm ci && npm run build

clean:
	rm -rf site/build site/.svelte-kit

.PHONY: all verify run demo site clean
