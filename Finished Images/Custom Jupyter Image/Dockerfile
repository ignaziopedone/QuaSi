FROM python:3.7

ENV APP_HOME /app
WORKDIR ${APP_HOME}

COPY . .
RUN pip install -r requirements.txt

CMD ["./launch.sh"]