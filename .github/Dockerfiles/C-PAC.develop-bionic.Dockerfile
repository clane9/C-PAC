LABEL org.opencontainers.image.description "Full C-PAC image"
FROM ghcr.io/fcp-indi/c-pac/stage-base:standard-v1.8.4.dev
USER root

# install C-PAC
COPY . /code
RUN pip install -e /code
# set up runscript
COPY dev/docker_data /code/docker_data
RUN rm -Rf /code/docker_data/Dockerfiles && \
    mv /code/docker_data/* /code && \
    rm -Rf /code/docker_data && \
    chmod +x /code/run.py && \
    chmod +x /code/run-with-freesurfer.sh
ENTRYPOINT ["/code/run-with-freesurfer.sh"]

# link libraries & clean up
RUN rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    ldconfig && \
    chmod 777 $(ls / | grep -v sys | grep -v proc)

# set user
USER c-pac_user
