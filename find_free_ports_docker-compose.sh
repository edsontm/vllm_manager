#!/usr/bin/env bash

set -euo pipefail

declare -A USED_PORTS=()
declare -A RESERVED_PORTS=()
declare -a FILES=()
declare -a CHANGES=()
declare -a FINAL_PORTS=()
declare -a OUTPUT_FILES=()

RANGE_START=0
RANGE_END=0
BIND_PREFIX=""
HOST_PORT_SPEC=""
CONTAINER_PART=""
PROTOCOL_SUFFIX=""

usage() {
  cat <<'EOF'
Usage: ./find_free_ports_docker-compose.sh [compose-file ...]

Scans Docker Compose files for published host ports that are already in use on the
machine, creates new Compose files with conflicting host ports rewritten to the
next free value, and prints the resulting host-port mappings.

If no files are passed, the script checks these files when present:
  - docker-compose.yml
  - docker-compose.override.yml
  - compose.yml
  - compose.override.yml

Generated files are written next to the originals with a .resolved suffix.
Existing .resolved files are overwritten on each run.
EOF
}

is_blank_or_comment() {
  local trimmed="${1#"${1%%[![:space:]]*}"}"
  [[ -z "$trimmed" || $trimmed == \#* ]]
}

parse_port_range() {
  local spec="$1"

  if [[ $spec =~ ^([0-9]+)-([0-9]+)$ ]]; then
    RANGE_START="${BASH_REMATCH[1]}"
    RANGE_END="${BASH_REMATCH[2]}"
  elif [[ $spec =~ ^([0-9]+)$ ]]; then
    RANGE_START="$spec"
    RANGE_END="$spec"
  else
    return 1
  fi

  if (( RANGE_START < 1 || RANGE_END > 65535 || RANGE_START > RANGE_END )); then
    return 1
  fi
}

reserve_port_spec() {
  local spec="$1"
  local port

  parse_port_range "$spec"
  for ((port = RANGE_START; port <= RANGE_END; port++)); do
    RESERVED_PORTS["$port"]=1
  done
}

mark_used_port_spec() {
  local spec="$1"
  local port

  if ! parse_port_range "$spec"; then
    return 1
  fi

  for ((port = RANGE_START; port <= RANGE_END; port++)); do
    USED_PORTS["$port"]=1
  done
}

range_is_available() {
  local spec="$1"
  local port

  parse_port_range "$spec"
  for ((port = RANGE_START; port <= RANGE_END; port++)); do
    if [[ -n ${USED_PORTS[$port]+x} || -n ${RESERVED_PORTS[$port]+x} ]]; then
      return 1
    fi
  done

  return 0
}

find_next_available_port_spec() {
  local original_spec="$1"
  local candidate_start
  local candidate_end
  local width
  local candidate_spec

  parse_port_range "$original_spec"
  candidate_start="$RANGE_START"
  width=$((RANGE_END - RANGE_START))

  while (( candidate_start + width <= 65535 )); do
    candidate_end=$((candidate_start + width))

    if (( width == 0 )); then
      candidate_spec="$candidate_start"
    else
      candidate_spec="${candidate_start}-${candidate_end}"
    fi

    if range_is_available "$candidate_spec"; then
      printf '%s\n' "$candidate_spec"
      return 0
    fi

    candidate_start=$((candidate_start + 1))
  done

  return 1
}

extract_host_port_parts() {
  local mapping="$1"
  local without_protocol="$mapping"
  local host_side

  BIND_PREFIX=""
  HOST_PORT_SPEC=""
  CONTAINER_PART=""
  PROTOCOL_SUFFIX=""

  if [[ $mapping =~ ^(.+)(/(tcp|udp|sctp))$ ]]; then
    without_protocol="${BASH_REMATCH[1]}"
    PROTOCOL_SUFFIX="${BASH_REMATCH[2]}"
  fi

  if [[ $without_protocol != *:* ]]; then
    return 1
  fi

  CONTAINER_PART="${without_protocol##*:}"
  host_side="${without_protocol%:*}"

  if [[ $host_side =~ ^(.*:)?([0-9]+(-[0-9]+)?)$ ]]; then
    BIND_PREFIX="${BASH_REMATCH[1]}"
    HOST_PORT_SPEC="${BASH_REMATCH[2]}"
    return 0
  fi

  return 1
}

load_used_ports() {
  local address
  local port
  local ports_line
  local raw_entry
  local entry
  local host_binding
  local host_port_spec
  local found_local_probe=0
  local -a entries=()

  if command -v ss >/dev/null 2>&1; then
    found_local_probe=1
    while IFS= read -r address; do
      [[ -z "$address" ]] && continue
      port="${address##*:}"
      [[ $port =~ ^[0-9]+$ ]] || continue
      USED_PORTS["$port"]=1
    done < <(ss -Hltnu | awk '{print $(NF-1)}')
  elif command -v lsof >/dev/null 2>&1; then
    found_local_probe=1
    while IFS= read -r port; do
      [[ $port =~ ^[0-9]+$ ]] || continue
      USED_PORTS["$port"]=1
    done < <(
      lsof -nP -iTCP -sTCP:LISTEN -iUDP 2>/dev/null |
        awk 'NR > 1 {split($9, parts, ":"); port = parts[length(parts)]; if (port ~ /^[0-9]+$/) print port}'
    )
  fi

  if (( found_local_probe == 0 )); then
    echo "Unable to inspect listening ports: install ss or lsof." >&2
    exit 1
  fi

  # Docker may publish ports via kernel NAT without a local listening socket,
  # so include host ports from running containers as occupied too.
  if command -v docker >/dev/null 2>&1; then
    while IFS= read -r ports_line; do
      [[ -z "$ports_line" ]] && continue
      IFS=',' read -r -a entries <<< "$ports_line"

      for raw_entry in "${entries[@]}"; do
        entry="${raw_entry#"${raw_entry%%[![:space:]]*}"}"
        entry="${entry%"${entry##*[![:space:]]}"}"

        [[ $entry == *"->"* ]] || continue
        host_binding="${entry%%->*}"

        if [[ $host_binding =~ :([0-9]+(-[0-9]+)?)$ ]]; then
          host_port_spec="${BASH_REMATCH[1]}"
          mark_used_port_spec "$host_port_spec" || true
        fi
      done
    done < <(docker ps --format '{{.Ports}}' 2>/dev/null || true)
  fi
}

collect_default_files() {
  local candidate

  for candidate in docker-compose.yml docker-compose.override.yml compose.yml compose.override.yml; do
    if [[ -f $candidate ]]; then
      FILES+=("$candidate")
    fi
  done
}

build_output_file_path() {
  local file="$1"
  local directory
  local base_name
  local stem
  local extension

  if [[ $file == */* ]]; then
    directory="${file%/*}"
  else
    directory="."
  fi

  base_name="${file##*/}"
  if [[ $base_name == *.* ]]; then
    stem="${base_name%.*}"
    extension=".${base_name##*.}"
  else
    stem="$base_name"
    extension=""
  fi

  printf '%s\n' "${directory}/${stem}.resolved${extension}"
}

process_file() {
  local file="$1"
  local tmp_file
  local output_file
  local line
  local line_no=0
  local indent=0
  local current_service=""
  local services_indent=-1
  local ports_indent=-1
  local in_services=0
  local in_ports=0
  local changed=0
  local prefix
  local quote
  local mapping
  local suffix
  local updated_mapping
  local new_host_port_spec
  local double_quoted_item_pattern='^([[:space:]]*-[[:space:]]*)"([^"]+)"([[:space:]]*(#.*)?)$'
  local single_quoted_item_pattern="^([[:space:]]*-[[:space:]]*)'([^']+)'([[:space:]]*(#.*)?)$"
  local unquoted_item_pattern='^([[:space:]]*-[[:space:]]*)([^[:space:]#]+)([[:space:]]*(#.*)?)$'

  tmp_file="$(mktemp)"
  output_file="$(build_output_file_path "$file")"

  while IFS= read -r line || [[ -n $line ]]; do
    ((line_no += 1))
    indent=0
    if [[ $line =~ ^([[:space:]]*) ]]; then
      indent=${#BASH_REMATCH[1]}
    fi

    if (( in_services == 0 )); then
      if [[ $line =~ ^([[:space:]]*)services:[[:space:]]*$ ]]; then
        in_services=1
        services_indent=${#BASH_REMATCH[1]}
        current_service=""
      fi
    else
      if ! is_blank_or_comment "$line" && (( indent <= services_indent )); then
        in_services=0
        current_service=""
      elif [[ $line =~ ^([[:space:]]*)([A-Za-z0-9._-]+):[[:space:]]*$ ]]; then
        if (( ${#BASH_REMATCH[1]} == services_indent + 2 )); then
          current_service="${BASH_REMATCH[2]}"
        fi
      fi
    fi

    if (( in_ports == 0 )); then
      if [[ $line =~ ^([[:space:]]*)ports:[[:space:]]*$ ]]; then
        in_ports=1
        ports_indent=${#BASH_REMATCH[1]}
      fi
    else
      if ! is_blank_or_comment "$line" && (( indent <= ports_indent )); then
        in_ports=0
      fi
    fi

    if (( in_ports == 1 )); then
      prefix=""
      quote=""
      mapping=""
      suffix=""

      if [[ $line =~ $double_quoted_item_pattern ]]; then
        prefix="${BASH_REMATCH[1]}"
        quote='"'
        mapping="${BASH_REMATCH[2]}"
        suffix="${BASH_REMATCH[3]}"
      elif [[ $line =~ $single_quoted_item_pattern ]]; then
        prefix="${BASH_REMATCH[1]}"
        quote="'"
        mapping="${BASH_REMATCH[2]}"
        suffix="${BASH_REMATCH[3]}"
      elif [[ $line =~ $unquoted_item_pattern ]]; then
        prefix="${BASH_REMATCH[1]}"
        mapping="${BASH_REMATCH[2]}"
        suffix="${BASH_REMATCH[3]}"
      fi

      if [[ -n $mapping ]] && extract_host_port_parts "$mapping"; then
        new_host_port_spec="$HOST_PORT_SPEC"

        if ! range_is_available "$HOST_PORT_SPEC"; then
          if ! new_host_port_spec="$(find_next_available_port_spec "$HOST_PORT_SPEC")"; then
            rm -f -- "$tmp_file"
            echo "Unable to find an available replacement for host port spec $HOST_PORT_SPEC in $file." >&2
            exit 1
          fi
        fi

        reserve_port_spec "$new_host_port_spec"
        updated_mapping="${BIND_PREFIX}${new_host_port_spec}:${CONTAINER_PART}${PROTOCOL_SUFFIX}"
        FINAL_PORTS+=("$output_file|$line_no|${current_service:-unknown}|$updated_mapping")

        if [[ $updated_mapping != "$mapping" ]]; then
          line="${prefix}${quote}${updated_mapping}${quote}${suffix}"
          CHANGES+=("$file|$output_file|$line_no|${current_service:-unknown}|$mapping|$updated_mapping")
          changed=1
        fi
      fi
    fi

    printf '%s\n' "$line" >> "$tmp_file"
  done < "$file"

  mv -- "$tmp_file" "$output_file"
  OUTPUT_FILES+=("$file|$output_file|$changed")
}

print_summary() {
  local entry
  local file
  local output_file
  local line
  local service
  local old_mapping
  local new_mapping
  local mapping
  local changed

  echo "Scanned compose files:"
  for file in "${FILES[@]}"; do
    echo " - $file"
  done

  echo
  echo "Generated compose files:"
  for entry in "${OUTPUT_FILES[@]}"; do
    IFS='|' read -r file output_file changed <<< "$entry"
    if [[ $changed == "1" ]]; then
      echo " - ${output_file} (from ${file}, resolved conflicting ports)"
    else
      echo " - ${output_file} (from ${file}, no port changes needed)"
    fi
  done

  echo
  if (( ${#CHANGES[@]} == 0 )); then
    echo "No conflicting published host ports were found. Original files were copied into generated files unchanged."
  else
    echo "Resolved conflicting host-port mappings:"
    for entry in "${CHANGES[@]}"; do
      IFS='|' read -r file output_file line service old_mapping new_mapping <<< "$entry"
      echo " - ${service} (${file}:${line} -> ${output_file}): ${old_mapping} -> ${new_mapping}"
    done
  fi

  echo
  if (( ${#FINAL_PORTS[@]} == 0 )); then
    echo "No published host-port mappings were found in the provided compose files."
    return 0
  fi

  echo "Published host-port mappings in generated files:"
  for entry in "${FINAL_PORTS[@]}"; do
    IFS='|' read -r output_file line service mapping <<< "$entry"
    echo " - ${service} (${output_file}:${line}): ${mapping}"
  done
}

main() {
  local file

  if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
    usage
    exit 0
  fi

  if (( $# > 0 )); then
    FILES=("$@")
  else
    collect_default_files
  fi

  if (( ${#FILES[@]} == 0 )); then
    echo "No Docker Compose files were found to process." >&2
    exit 1
  fi

  for file in "${FILES[@]}"; do
    if [[ ! -f $file ]]; then
      echo "Compose file not found: $file" >&2
      exit 1
    fi
  done

  load_used_ports

  for file in "${FILES[@]}"; do
    process_file "$file"
  done

  print_summary
}

main "$@"