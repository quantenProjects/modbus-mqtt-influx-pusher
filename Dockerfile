FROM python:slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

ENTRYPOINT ["python3"]
CMD ["-m", "mqip", "/etc/config.ini"]

