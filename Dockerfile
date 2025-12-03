FROM python:slim

# Set environment variables for non-interactive installations
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

ARG apt_cacher
RUN if [ -n "$apt_cacher" ] ; then \
    echo "Acquire::http { Proxy \"http://${apt_cacher}:3142\"; };" >> /etc/apt/apt.conf.d/01proxy ; \
    fi

# Update package list and install necessary dependencies
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends \
#         default-mysql-client \
#     && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY ./app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app .

RUN python -m compileall -f . \
    && chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
