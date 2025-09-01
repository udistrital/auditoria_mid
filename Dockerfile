FROM python:3.9

COPY entrypoint.sh entrypoint.sh

RUN chmod +x entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

ADD requirements.txt .

RUN pip install -r requirements.txt

RUN apt-get update

RUN apt-get install poppler-utils -y

COPY conf/** /conf/

COPY controllers/** /controllers/

COPY services/** /services/

COPY models/** /models/

COPY routers/** /routers/

ADD api.py .

#CMD [ "python", "./api.py" ]
