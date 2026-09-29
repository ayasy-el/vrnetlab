VENDOR=Juniper
NAME=cRPD
IMAGE_FORMAT=tgz
IMAGE_GLOB=*.tgz *.tar.gz *.qcow2

# Exclude already built .docker.tar.gz archives
IMAGES=$(filter-out %.docker.tar.gz, $(wildcard $(IMAGE_GLOB)))

-include ../../makefile-sanity.include

all: docker-image

ifeq ($(strip $(IMAGES)),)
docker-image:
	@echo "ERROR: you have no $(IMAGE_FORMAT) ($(IMAGE_GLOB)) image"
	@echo "Usage: put the $(VENDOR) $(NAME) $(IMAGE_FORMAT) image in this directory and run:"
	@echo "  make"
	@exit 1
else
docker-image:
	@for IMAGE in $(IMAGES); do \
		echo "Making $$IMAGE"; \
		python3 convert_crpd.py "$$IMAGE"; \
	done
endif

clean:
	@echo "--> Cleaning generated archives"
	-rm -f *.docker.tar.gz
	-rm -rf /tmp/crpd_*

.PHONY: all docker-image clean
