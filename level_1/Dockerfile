# =====================================================
# WEB-01 : "Breach The Terminal"  -  Easy Web Security
# =====================================================
# Uses the official "unprivileged" nginx image: runs as a
# non-root user (uid 101) and listens on port 8080 instead
# of 80, with its temp/cache files under /tmp.
#
# NOTE: no "rm -rf /usr/share/nginx/html/*" step here - the
# base image already switches to the non-root nginx user, so
# a RUN command can't delete its root-owned default files.
# COPY doesn't have that restriction (the builder writes the
# layer directly), so it simply overwrites index.html. The
# leftover default 50x.html is harmless - it's never linked
# from the challenge and only nginx's own built-in error page.

FROM nginxinc/nginx-unprivileged:alpine

COPY site/ /usr/share/nginx/html/

EXPOSE 8080
