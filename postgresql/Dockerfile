FROM postgres:12-alpine

# Include extra setup scripts (eg datastore)
ADD --chmod=755 docker-entrypoint-initdb.d /docker-entrypoint-initdb.d

# Convert CRLF (Windows) → LF (Linux) in case code was checked out on Windows
RUN set -eux; \
    find /docker-entrypoint-initdb.d -type f -name '*.sh' -exec sed -i "s/\r$//" {} +; \
    chmod +x /docker-entrypoint-initdb.d/*.sh
