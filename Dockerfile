FROM rg.fr-par.scw.cloud/djnd/parladata:47860eb2a691c15e394da58ee9a6e2a38d000997

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
