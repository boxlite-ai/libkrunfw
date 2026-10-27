.PHONY: clean

all: krunfw_measurement

krunfw_measurement: krunfw_measurement.c
	gcc -o $@ $< -lcrypto

clean:
	rm -rf krunfw_measurement

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
PYTHON ?= python3
DIND_SOURCES ?= $(ROOT)/$(shell sed -n 's/^KERNEL_VERSION = //p' "$(ROOT)/Makefile")
DIND_IMAGE ?= $(ROOT)/libkrunfw-kernel-dind-$(shell uname -m).bin
DIND_OUTPUT ?= $(ROOT)/dist/dind

.PHONY: package-dind test-dind-library
package-dind:
	PYTHON="$(PYTHON)" CC="$(CC)" bash "$(ROOT)/utils/package-dind-library.sh" "$(DIND_SOURCES)" "$(DIND_IMAGE)" "$(DIND_OUTPUT)"

test-dind-library:
	"$(PYTHON)" "$(ROOT)/utils/test_dind_library.py"
