#!/usr/bin/env bash

resolve_proxy_value() {
  local primary_lower="$1"
  local primary_upper="$2"
  local fallback_lower="$3"
  local fallback_upper="$4"

  if [[ -n "${!primary_lower:-}" ]]; then
    printf '%s' "${!primary_lower}"
    return 0
  fi
  if [[ -n "${!primary_upper:-}" ]]; then
    printf '%s' "${!primary_upper}"
    return 0
  fi
  if [[ -n "${!fallback_lower:-}" ]]; then
    printf '%s' "${!fallback_lower}"
    return 0
  fi
  if [[ -n "${!fallback_upper:-}" ]]; then
    printf '%s' "${!fallback_upper}"
    return 0
  fi
  return 1
}

container_host_alias() {
  local runtime="$1"
  case "${runtime}" in
    podman)
      printf '%s' "host.containers.internal"
      ;;
    *)
      printf '%s' "host.docker.internal"
      ;;
  esac
}

rewrite_proxy_url_for_container() {
  local runtime="$1"
  local proxy_url="$2"
  local host_alias
  host_alias="$(container_host_alias "${runtime}")"

  proxy_url="${proxy_url/#http:\/\/127.0.0.1/http://${host_alias}}"
  proxy_url="${proxy_url/#https:\/\/127.0.0.1/https://${host_alias}}"
  proxy_url="${proxy_url/#http:\/\/localhost/http://${host_alias}}"
  proxy_url="${proxy_url/#https:\/\/localhost/https://${host_alias}}"
  printf '%s' "${proxy_url}"
}

print_container_proxy_args() {
  local runtime="$1"
  local proxy_value=""
  local normalized_proxy=""
  local no_proxy_value=""

  if proxy_value=$(resolve_proxy_value http_proxy HTTP_PROXY https_proxy HTTPS_PROXY); then
    normalized_proxy="$(rewrite_proxy_url_for_container "${runtime}" "${proxy_value}")"
    printf '%s\n' "-e" "http_proxy=${normalized_proxy}"
    printf '%s\n' "-e" "https_proxy=${normalized_proxy}"
  fi

  if no_proxy_value=$(resolve_proxy_value no_proxy NO_PROXY no_proxy NO_PROXY); then
    printf '%s\n' "-e" "no_proxy=${no_proxy_value}"
  fi
}
