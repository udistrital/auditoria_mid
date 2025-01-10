FROM alpine:3.15

# Instalar ping
RUN apk add --no-cache iputils

# Verificar la conexión a internet
RUN ping -c 4 google.com || (echo "No internet connection" && exit 1)

RUN pip install awscli

COPY entrypoint.sh entrypoint.sh

RUN chmod +x entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

ADD requirements.txt .

RUN pip install -r requirements.txt

RUN apt-get update

RUN apt-get install poppler-utils -y

COPY conf/** /conf/

COPY controllers/** /controllers/

COPY models/** /models/

COPY routers/** /routers/

COPY swagger/** /swagger/

ADD api.py .

#CMD [ "python", "./api.py" ]
