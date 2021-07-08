FROM rg.fr-par.scw.cloud/djnd/parladata:38f60ccce30758c9aa0e6b023b022e875e3b1491

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
