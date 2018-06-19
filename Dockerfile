FROM python:3.6

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install tox

ADD . /app