#!/usr/bin/env bash
# Generate self-signed certificates for LOCAL operator smoke testing of the
# remote M8 HTTPS setup. NOT for real participants — real participants need
# a publicly trusted certificate (see report EXTERNAL ACTION section).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTS_DIR="$REPO_ROOT/certs"
mkdir -p "$CERTS_DIR"

DAYS=365
CN="${CERT_CN:-localhost}"

openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$CERTS_DIR/privkey.pem" \
  -out "$CERTS_DIR/fullchain.pem" \
  -days "$DAYS" \
  -subj "/CN=$CN" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$CERTS_DIR/privkey.pem"
chmod 644 "$CERTS_DIR/fullchain.pem"

echo "Self-signed certs generated in $CERTS_DIR (CN=$CN, days=$DAYS)"
echo "  privkey.pem  (mode 600)"
echo "  fullchain.pem (mode 644)"
echo "NOTE: These are for local operator smoke testing ONLY."
