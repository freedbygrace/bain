###########
# BUILDER #
###########

# pull official base image
FROM python AS builder

# set work directory
WORKDIR /usr/src/bolls

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# install psycopg2 dependencies
RUN apt update -y \
    && apt install -y postgresql postgresql-contrib netcat-traditional

# lint
RUN pip install --upgrade pip

# install dependencies
COPY ./requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/bolls/wheels -r requirements.txt


#########
# FINAL #
#########

# pull official base image
FROM python

# create the appropriate directories
ENV HOME=/app
ENV APP_HOME=/app
RUN mkdir -p $APP_HOME/static $APP_HOME/data
WORKDIR $APP_HOME

# install dependencies
RUN apt update -y && apt install -y netcat-traditional unzip curl
COPY --from=builder /usr/src/bolls/wheels /wheels
COPY --from=builder /usr/src/bolls/requirements.txt .
RUN pip install --no-cache /wheels/*

# copy entrypoint.sh
COPY ./entrypoint.sh $APP_HOME
RUN chmod +x $APP_HOME/entrypoint.sh

# copy project (includes data/translations/ and data/dictionaries/)
COPY . $APP_HOME

# Make everything world-readable so any UID can run
RUN chmod -R a+rX $APP_HOME

# Container runs as PUID:PGID via docker-compose user: directive
ENTRYPOINT ["/app/entrypoint.sh"]