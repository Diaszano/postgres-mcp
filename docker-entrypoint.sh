#!/bin/bash
set -e

remap=${DATABASE_DOCKER_REMAP_LOCALHOST:-false}
case "$remap" in
    true|false) ;;
    *) echo "Invalid DATABASE_DOCKER_REMAP_LOCALHOST value; expected true or false." >&2; exit 2 ;;
esac

docker_host=""
if [[ "$remap" == true ]]; then
    if ping -c 1 -w 1 host.docker.internal >/dev/null 2>&1; then
        docker_host=host.docker.internal
    elif ping -c 1 -w 1 172.17.0.1 >/dev/null 2>&1; then
        docker_host=172.17.0.1
    else
        echo "Cannot determine Docker host; database host was left unchanged." >&2
    fi
fi

remap_uri() {
    python - "$1" "$docker_host" <<'PY'
import sys
from urllib.parse import urlsplit

uri, docker_host = sys.argv[1:]
if not docker_host:
    print(uri)
    raise SystemExit
try:
    parsed = urlsplit(uri)
    netloc = parsed.netloc
    host_port = netloc.rsplit("@", 1)[-1]
    host = host_port.partition(":")[0]
    if parsed.scheme not in ("postgres", "postgresql") or host.lower() != "localhost":
        print(uri)
        raise SystemExit
except ValueError:
    print(uri)
    raise SystemExit

scheme_end = uri.find("://") + 3
authority_end = min((i for i in (uri.find("/", scheme_end), uri.find("?", scheme_end), uri.find("#", scheme_end)) if i >= 0), default=len(uri))
authority = uri[scheme_end:authority_end]
userinfo_length = authority.rfind("@") + 1
host_start = scheme_end + userinfo_length
print(uri[:host_start] + docker_host + uri[host_start + len(host):])
PY
}

processed_args=("$1")
shift
for arg in "$@"; do
    processed_args+=("$(remap_uri "$arg")")
done

if [[ -n "${DATABASE_URI:-}" ]]; then
    DATABASE_URI=$(remap_uri "$DATABASE_URI")
    export DATABASE_URI
fi

has_sse=false
has_sse_host=false
for i in "${!processed_args[@]}"; do
    arg=${processed_args[$i]}
    if [[ "$arg" == "--transport=sse" || ( "$arg" == "--transport" && "${processed_args[$((i + 1))]:-}" == "sse" ) ]]; then
        has_sse=true
    elif [[ "$arg" == --sse-host* ]]; then
        has_sse_host=true
    fi
done
if [[ "$has_sse" == true && "$has_sse_host" == false ]]; then
    processed_args+=("--sse-host=0.0.0.0")
fi

exec "${processed_args[@]}"
