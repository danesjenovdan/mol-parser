FROM rg.fr-par.scw.cloud/djnd/parladata:cc58db872e8999270c0dbb92216747250c6ca6bb

RUN apt-get update && \
    apt-get upgrade -y

RUN apt-get install libpoppler-cpp-dev -y

RUN /usr/local/bin/python -m pip install --upgrade pip

RUN mkdir /parser
WORKDIR /parser

COPY requirements.txt /parser/
RUN pip install -r requirements.txt

COPY . /parser

CMD bash run_parser_flow.sh
