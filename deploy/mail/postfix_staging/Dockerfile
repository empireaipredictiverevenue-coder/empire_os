FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive
RUN printf 'postfix postfix/main_mailer_type select Local only\npostfix postfix/mailname string mx-stage.mail.empire-ai.co.uk\n' | debconf-set-selections \
  && apt-get update \
  && apt-get install -y --no-install-recommends postfix rspamd python3 python3-dkim python3-dnslib openssl ca-certificates \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/empire
COPY owned_postfix_staging_profile.py /opt/empire/empire_os/owned_postfix_staging_profile.py
COPY probe_postfix_staging_smtp_rcpt.py /opt/empire/scripts/probe_postfix_staging_smtp_rcpt.py
COPY probe_postfix_synthetic_delivery.py /opt/empire/scripts/probe_postfix_synthetic_delivery.py
COPY owned_postfix_maildir_custody.py /opt/empire/empire_os/owned_postfix_maildir_custody.py
COPY probe_postfix_maildir_custody.py /opt/empire/scripts/probe_postfix_maildir_custody.py
COPY owned_postfix_rspamd_auth_stage.py /opt/empire/empire_os/owned_postfix_rspamd_auth_stage.py
COPY probe_postfix_milter_outage.py /opt/empire/scripts/probe_postfix_milter_outage.py
COPY probe_postfix_milter_online.py /opt/empire/scripts/probe_postfix_milter_online.py
COPY ci_rspamd_local_dns_fixture.py /opt/empire/scripts/ci_rspamd_local_dns_fixture.py
COPY ci_rspamd_alignment_probe.py /opt/empire/scripts/ci_rspamd_alignment_probe.py
COPY container-entrypoint.sh /opt/empire/container-entrypoint.sh
ENTRYPOINT ["/bin/bash", "/opt/empire/container-entrypoint.sh"]
