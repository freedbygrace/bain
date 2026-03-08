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

# create directory for the bolls user
RUN mkdir -p /home/bolls

# create the bolls user
RUN addgroup --system bolls \
    && adduser --system --ingroup bolls bollsuser

# create the appropriate directories
ENV HOME=/home/bolls
ENV BOLLS_HOME=/home/bolls/web
RUN mkdir $BOLLS_HOME
RUN mkdir $BOLLS_HOME/static
WORKDIR $BOLLS_HOME

# install dependencies
RUN apt update -y && apt install -y netcat-traditional unzip curl
COPY --from=builder /usr/src/bolls/wheels /wheels
COPY --from=builder /usr/src/bolls/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy Bible translation data (144 translations, ~1.1GB)
# These are pre-downloaded JSON files from Bolls.life API
COPY ./data/translations/ /app/data/translations/

# Copy dictionary data (Strong's Hebrew/Greek definitions, ~40MB)
COPY ./data/dictionaries/ /app/data/dictionaries/

# copy entrypoint.sh
COPY ./entrypoint.sh $BOLLS_HOME

# copy project
COPY . $BOLLS_HOME

# chown all the files to the bolls user
RUN chown -R bollsuser:bolls $BOLLS_HOME

# change to the bolls user
USER bollsuser

# run entrypoint.sh
ENTRYPOINT ["/home/bolls/web/entrypoint.sh"]