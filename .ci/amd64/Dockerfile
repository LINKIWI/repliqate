FROM docker.internal.kevinlin.info/infra/ci-base:0.3.0

ENV PYINSTALLER_VERSION 53b149eb96b88927df1e9728890a26b3895a62d1

RUN sudo apt-get update && sudo apt-get install -y \
    patchelf \
    python3-venv

# Reference: https://github.com/pyinstaller/pyinstaller/issues/5361#issuecomment-737181965
RUN wget -O pyinstaller.tar.gz https://github.com/pyinstaller/pyinstaller/archive/$PYINSTALLER_VERSION.tar.gz
RUN mkdir pyinstaller/
RUN tar xvf pyinstaller.tar.gz -C pyinstaller/ --strip-components=1
RUN cd pyinstaller/bootloader/ && CC="gcc -no-pie" python ./waf distclean all
RUN sudo mv pyinstaller/ /opt/
