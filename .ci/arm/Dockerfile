FROM multiarch/qemu-user-static:arm as qemu
FROM arm32v7/ubuntu:20.04

ENV PYINSTALLER_VERSION 53b149eb96b88927df1e9728890a26b3895a62d1

COPY --from=qemu /usr/bin/qemu-arm-static /usr/bin/

RUN apt-get update && apt-get install -y \
    patchelf \
    python3 \
    python3-pip \
    python3-venv \
    python-is-python3 \
    wget
RUN update-ca-certificates -f -v

RUN wget -O pyinstaller.tar.gz https://github.com/pyinstaller/pyinstaller/archive/$PYINSTALLER_VERSION.tar.gz
RUN mkdir pyinstaller/
RUN tar xvf pyinstaller.tar.gz -C pyinstaller/ --strip-components=1
RUN cd pyinstaller/bootloader/ && CC="gcc -no-pie" python ./waf distclean all
RUN mv pyinstaller/ /opt/
